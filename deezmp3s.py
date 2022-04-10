#!/usr/bin/env python
# -*- coding: utf-8 -*-
import binascii
import hashlib
import os
import sys

import arrow
import click
import eyed3
import eyed3.id3
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from eyed3.id3.frames import ImageFrame
from loguru import logger
from mutagen.flac import FLAC as MUTA_FLAC, Picture

import settings
import utils

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHT' \
             'ML, like Gecko) Chrome/72.0.3626.121 Safari/537.36'

MP3_320 = '3'
FLAC = '9'


class Packer(object):
    def __init__(self, album_id, flac):
        self.album_id = album_id
        self.flac = flac

        self.csrf_token = None

        # path to album art image
        self.album_art = None
        self.album_artist = None
        self.album_title = None
        self.num_tracks = None
        self.publisher = None
        self.genre = None
        self.year = None

        self.release_name = None
        self.folder_path = None
        self.base_file_name = None
        self.sfv = {}

        self.session = requests.Session()
        self.session.headers.update({'user-agent': USER_AGENT})
        self.session.cookies.update({'arl': settings.ARL})

    def get_blowfish_key(self, song_id):
        m = hashlib.md5()
        m.update(bytes([ord(x) for x in song_id]))

        md5 = m.hexdigest()
        return bytes(
            (
                [
                    (ord(md5[i]) ^ ord(md5[i + 16]) ^ ord(settings.BLOWFISH_KEY[i]))
                    for i in range(16)
                ]
            )
        )

    def get_track_url(self, secret_info, quality):
        char = b'\xa4'.decode('unicode_escape')

        step1 = char.join(
            (
                secret_info['MD5_ORIGIN'],
                quality,
                secret_info['SNG_ID'],
                secret_info['MEDIA_VERSION']
            )
        )

        m = hashlib.md5()
        m.update(bytes([ord(x) for x in step1]))

        step2 = m.hexdigest() + char + step1 + char
        step2 = step2.ljust(80, ' ')

        cipher = Cipher(
            algorithms.AES(settings.AES_SECRET),
            modes.ECB(),
            default_backend()
        )
        encryptor = cipher.encryptor()

        return 'https://e-cdns-proxy-{}.dzcdn.net/mobile/1/{}'.format(
            secret_info['MD5_ORIGIN'][0],
            encryptor.update(bytes([ord(x) for x in step2])).hex()
        )

    def download_track(self, file_path, url, blowfish_key):
        mp3 = self.session.get(url, stream=True)

        if mp3.status_code != requests.codes.ok:
            return logger.error(
                f'Failed to download track; code: {mp3.status_code}'
            )

        with open(file_path, 'wb') as f:
            for i, chunk in enumerate(mp3.iter_content(2048)):
                if i % 3 > 0 or len(chunk) < 2048:
                    f.write(chunk)
                else:
                    cipher = Cipher(
                        algorithms.Blowfish(blowfish_key),
                        modes.CBC(bytes([i for i in range(8)])),
                        default_backend()
                    )
                    decryptor = cipher.decryptor()
                    f.write(decryptor.update(chunk) + decryptor.finalize())

    def get_checksum(self, file_path):
        buf = open(file_path, 'rb').read()
        return '{:08x}'.format(binascii.crc32(buf) & 0xFFFFFFFF)

    def tag_flac(self, file_path, track_info):
        flac = MUTA_FLAC(file_path)
        flac.delete()

        flac['artist'] = track_info['artist']['name']
        flac['albumartist'] = self.album_artist
        flac['album'] = self.album_title
        flac['title'] = track_info['title']
        flac['tracknumber'] = str(track_info['track_position'])
        flac['tracktotal'] = str(self.num_tracks)
        flac['genre'] = self.genre
        flac['date'] = str(self.year)
        flac['publisher'] = self.publisher

        if settings.EMBED_ARTWORK and self.album_art:
            cover_art = Picture()
            cover_art.type = 3
            cover_art.data = open(self.album_art, 'rb').read()
            flac.add_picture(cover_art)

        flac.save()

    def tag_mp3(self, file_path, track_info):
        mp3 = eyed3.load(file_path)
        mp3.initTag()

        mp3.tag.artist = track_info['artist']['name']
        mp3.tag.album_artist = self.album_artist
        mp3.tag.album = self.album_title
        mp3.tag.title = track_info['title']
        mp3.tag.track_num = (track_info['track_position'], self.num_tracks)
        mp3.tag.genre = eyed3.id3.Genre(self.genre)
        mp3.tag.recording_date = self.year
        mp3.tag.publisher = self.publisher

        if settings.EMBED_ARTWORK and self.album_art:
            mp3.tag.images.set(
                ImageFrame.FRONT_COVER,
                open(self.album_art, 'rb').read(),
                'image/jpeg'
            )

        mp3.tag.save(version=eyed3.id3.ID3_V1_1)
        mp3.tag.save(version=eyed3.id3.ID3_V2_3)

    def create_sfv_and_m3u(self):
        sfv_name = '{}.sfv'.format(self.base_file_name)
        sfv_path = os.path.join(self.folder_path, sfv_name)

        m3u_name = '{}.m3u'.format(self.base_file_name)
        m3u_path = os.path.join(self.folder_path, m3u_name)

        with open(sfv_path, 'w') as sfv, open(m3u_path, 'w') as m3u:
            for mp3_name, checksum in sorted(self.sfv.items()):
                sfv.write('{} {}\n'.format(mp3_name, checksum))
                m3u.write('{}\n'.format(mp3_name))

    def process_track(self, track):
        """
        :param track: example:
        {'artist': {'id': 7497634,
                          'name': 'Sam Gellaitry',
                          'tracklist': 'https://api.deezer.com/artist/7497634/top?limit=50',
                          'type': 'artist'},
               'disk_number': 1,
               'duration': 265,
               'explicit_content_cover': 2,
               'explicit_content_lyrics': 2,
               'explicit_lyrics': False,
               'id': 657018782,
               'isrc': 'GBKPL1941872',
               'link': 'https://www.deezer.com/track/657018782',
               'preview': 'https://cdns-preview-a.dzcdn.net/stream/c-aacfed277635022413df3347b87d3098-8.mp3',
               'rank': 290909,
               'readable': True,
               'title': 'Viewfinder',
               'title_short': 'Viewfinder',
               'title_version': '',
               'track_position': 2,
               'type': 'track'}
        :type track: dict
        :return:
        :rtype:
        """
        params = {
            'api_version': '1.0',
            'api_token': self.csrf_token,
            'input': '3',
            'method': 'deezer.pageTrack'
        }
        secret_info = self.session.post(
            url=settings.PRIVATE_API_URL,
            params=params,
            json={'SNG_ID': track['id']}
        ).json()['results']['DATA']

        extension = 'flac' if self.flac else 'mp3'

        file_name = '{:02d}-{}-{}-{}.{}'.format(
            track['track_position'],
            track['artist']['name'],
            track['title'],
            utils.random_str(),
            extension
        ).lower()
        file_name = utils.clean(file_name)

        file_path = os.path.join(self.folder_path, file_name)

        logger.debug('Downloading: {}'.format(file_name))

        quality = FLAC if self.flac else MP3_320

        decrypted_url = self.get_track_url(secret_info, quality)
        blowfish_key = self.get_blowfish_key(secret_info['SNG_ID'])

        self.download_track(file_path, decrypted_url, blowfish_key)
        if self.flac:
            self.tag_flac(file_path, track)
        else:
            self.tag_mp3(file_path, track)

        self.sfv[file_name] = self.get_checksum(file_path)

    def set_csrf_token(self):
        params = {
            'api_version': '1.0',
            'api_token': 'null',
            'input': 3,
            'method': 'deezer.getUserData'
        }

        resp = self.session.post(
            url=settings.PRIVATE_API_URL,
            params=params
        )

        if resp.status_code != requests.codes.ok:
            logger.error(
                'Non 200 response when trying to get csrf token: {}'.format(
                    resp.status_code
                )
            )
            sys.exit()

        data = resp.json()['results']

        if not data['USER']['USER_ID']:
            logger.error('arl is invalid')
            sys.exit()

        self.csrf_token = data['checkForm']

    def download_album_art(self, url):
        art = self.session.get(url, stream=True)

        album_art_file_name = '{}.jpg'.format(self.base_file_name)
        album_art_path = os.path.join(self.folder_path, album_art_file_name)

        with open(album_art_path, 'wb') as f:
            for chunk in art.iter_content(1024):
                f.write(chunk)

        logger.debug('Finished downloading album art')

        return album_art_path

    def step_1(self):
        resp = self.session.get('{}/album/{}/'.format(settings.API_URL, self.album_id))

        data = resp.json()
        self.album_title = data['title']

        download_folder = settings.DOWNLOAD_FOLDER

        release_date = arrow.get(data['release_date'], 'YYYY-MM-DD')
        self.year = release_date.year

        unformatted_folder_name = '{}-{}-WEB-{}-{}'.format(
            data['artist']['name'],
            self.album_title,
            self.year,
            settings.GROUP_NAME
        )

        self.release_name = utils.clean(unformatted_folder_name)

        logger.info('Packing: {}'.format(self.release_name))

        self.folder_path = os.path.join(download_folder, self.release_name)

        unformatted_base_file_name = '00-{}-{}-web-{}'.format(
            data['artist']['name'],
            self.album_title,
            self.year
        ).lower()

        self.base_file_name = utils.clean(unformatted_base_file_name)

        os.makedirs(self.folder_path)

        return data

    def step_2(self, album_info):
        try:
            self.genre = album_info['genres']['data'][0]['name']
        except IndexError:
            pass
        self.num_tracks = album_info['nb_tracks']
        self.album_artist = album_info['artist']['name']
        self.publisher = album_info['label']

        for i, track in enumerate(album_info['tracks']['data'], start=1):
            track['track_position'] = i

        for track in album_info['tracks']['data']:
            self.process_track(track)

    def run(self):
        self.set_csrf_token()

        album_info = self.step_1()

        if album_info['cover_big']:
            self.album_art = self.download_album_art(album_info['cover_big'])

        self.step_2(album_info)

        self.create_sfv_and_m3u()


@click.command(help='Get deeeeeez mp3s!')
@click.argument('album_id')
@click.option('--flac', '-f', is_flag=True, help='Download FLAC')
def cli(album_id, flac):
    packer = Packer(album_id, flac)
    packer.run()


if __name__ == '__main__':
    cli()
