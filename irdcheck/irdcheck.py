#!/usr/bin/env python3

import gzip
import sys
import os
import io
from construct.core import ConstError
import argparse

import ird
import iso

class FileTree:
    def __init__(self):
        self.files = []

    def _print_files(self, files, prefix, attrs, print_dirs):
        for e in files:
            tmp = []
            for attr, length in attrs.items():
                if attr == 'name':
                    tmp += [f"{prefix+e[attr]:{length}}"]
                else:
                    tmp += [f"{e[attr]:{length}}"]
            if print_dirs or 'content' not in e:
                print(" | ".join(tmp))
            if 'content' in e:
                self._print_files(e['content'], f"{prefix}{e['name']}/", attrs, print_dirs)

    def _get_max_print_widths(self, files, attrs, prefix=""):
        for e in files:
            if 'content' in e:
                sub = self._get_max_print_widths(e['content'],
                        attrs, f"{prefix}{e['name']}/")
                for attr, value in attrs.items():
                    attrs[attr] = max(value, sub[attr]) 
            else:
                for attr, value in attrs.items():
                    if attr == 'name':
                        n = len(f"{prefix}{e['name']}")
                    else:
                        n = len(str(e[attr]))
                    attrs[attr] = max(value, n) 
        return attrs

    def print_files(self, attrs, print_dirs=False):
        prefix = ''
        attrs_lens = self._get_max_print_widths(self.files,
                {x:0 for x in attrs}, prefix)
        header = []
        for attr, length in attrs_lens.items():
            header += [f"{attr.capitalize():{length}}"]
        print(" | ".join(header))
        self._print_files(self.files, prefix, attrs_lens, print_dirs)

class IrdFile(FileTree):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        f = gzip.open(filename)

        self.content = None
        self.gzipped = True
        while self.content is None and f is not None:
            try:
                self.parse(f)
            except OSError: # not gzip
                if self.gzipped:
                    self.gzipped = False
                    f.close()
                    f = open(filename, "rb")
                    continue
                else:
                    raise
            f.close()
            f = None

        if self.content is None:
            return

    def parse(self, handle):
        try:
            magic_bytes = handle.peek(4) # fails if not gzip
            ird.IrdMagic.parse(magic_bytes) # fails if incorrect magic
        except ConstError as e:
            raise Exception(f"Incorrect magic bytes: {e}") from None

        self.content = ird.IrdBase.parse_stream(handle)

        self.parse_header()

        self.map_md5sums(self.files)

    def parse_header(self):
        hdr = io.BytesIO(self.content.header)
        parsed = iso.ParseIso(hdr, parse_iso=False)
        self.files = parsed['udf']


    def verify_dir(self, dir_files, ird_files):
        pass

    def check(self, game_dir):
        dir_files = self.build_file_list(game_dir)
        print(dir_files)

    def map_md5sums(self, dir):
        for file in dir:
            file['hash'] = ''
            if 'content' in file: # recurse directories
                self.map_md5sums(file['content'])
            else:
                for ird_file in self.content.files:
                    sector = file['sector']
                    if sector == ird_file.sector:
                        file['hash'] = ird_file.hash.hex()
                        break
                if 'hash' not in file:
                    print(f"IRD damaged! File {file['sector']} not found in UDF header")

    def id(self):
        return self.content.game_id

    def name(self):
        return self.content.game_name

    def print_files(self):
        super().print_files(['name', 'size', 'sector', 'hash'])

    def print_header(self):
        print(f"{self.id()} - {self.name()}")

class GameDir(FileTree):
    def __init__(self, game_dir):
        super().__init__()
        self.dir = game_dir
        self.build_file_list()

    def get_file_by_path(self, path):
        content = self.files
        for d in filter(lambda x: x, path.split("/")):
            elem = next(filter(lambda x: x['name'] == d, content), None)
            if elem is not None:
                content = elem['content']
            else:
                return None
        return content

    def build_file_list(self):
        for root, dirs, files in os.walk(self.dir):
            current_dir = root[len(self.dir):]
            content = self.get_file_by_path(current_dir)
            if content is None:
                print("bug: {} not found".format(current_dir))
                break

            for d in dirs:
                tmp = {'name': d, 'size': '', 'content': []}
                content += [tmp]
                
            for f in files:
                tmp = {'name': f,
                    'size': os.stat(os.path.join(root, f)).st_size}
                content += [tmp]

    def print_files(self):
        super().print_files(['name', 'size'])

def parse_args():
    parser = argparse.ArgumentParser(description='Read IRD files and test files for conformance')
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument('-m', '--md5sums',
            dest='action', const='md5sum', action='store_const',
            help='Print IRD content in a format compatible to md5sum')
    action_group.add_argument('-p', '--print',
            dest='action', const='print', action='store_const',
            help='Print IRD content in detailed human-readable form (default if only IRD given)')
    action_group.add_argument('-c', '--check',
            dest='action', const='check', action='store_const',
            help='Verify game directory against IRD (default if game dir given)')
    parser.add_argument('-v', '--verbose', action='store_true',
            help='Print more information')
    parser.add_argument('ird_file', metavar='file.ird',
            help='IRD file to use')
    parser.add_argument('game_dir', metavar='game_dir', nargs='?',
            help='Directory with game files to be verified')
    parser.set_defaults(action='default')
    args = parser.parse_args()
    if args.action == 'default':
        if args.game_dir is not None:
            args.action = 'check'
        else:
            args.action = 'print'
    if args.action == 'check' and args.game_dir is None:
        parser.print_usage()
        print("error: game_dir is required for checking")
        sys.exit(2)
    return args

if __name__ == "__main__":
    args = parse_args()

    ird = IrdFile(args.ird_file)
    #ird.print_files()
    game = GameDir(args.game_dir)
    #game.print_files()
    #sys.exit(0)

    if args.action == 'print':
        ird.print_header()
        ird.print_files()
    elif args.action == 'md5sum':
        ird.print_md5sum()
    elif args.action == 'check':
        ird.print_header()
        ird.check()
