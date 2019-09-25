#!/usr/bin/env python3

import gzip
import sys
import os
import io
from construct.core import ConstError
import argparse
import hashlib
from functools import partial

import ird
import iso

class FileTree:
    def __init__(self):
        self.files = []

    def _print_files(self, files, prefix, attrs, print_dirs, separator):
        for e in files:
            tmp = []
            for attr, length in attrs.items():
                if attr == 'name':
                    tmp += [f"{prefix+e[attr]:{length}}"]
                else:
                    tmp += [f"{e[attr]:{length}}"]
            if print_dirs or 'content' not in e:
                print(separator.join(tmp))
            if 'content' in e:
                self._print_files(e['content'], f"{prefix}{e['name']}/",
                    attrs, print_dirs, separator)

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

    def print_files(self, attrs, print_dirs=False, separator=' | ', print_header=True):
        prefix = ''
        attrs_lens = self._get_max_print_widths(self.files,
                {x:0 for x in attrs}, prefix)
        if print_header:
            header = []
            for attr, length in attrs_lens.items():
                header += [f"{attr.capitalize():{length}}"]
            print(separator.join(header))
        self._print_files(self.files, prefix, attrs_lens, print_dirs, separator)

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

    def print_md5sum(self):
        super().print_files(['hash', 'name'], separator='  ', print_header=False)

    def print_header(self):
        print(f"{self.id()} - {self.name()}")

class GameDir(FileTree):
    def __init__(self, game_dir):
        super().__init__()
        self.dir = game_dir
        self.build_file_list()

        self.files_ird = 0
        self.files_disk = 0
        self.files_ok = 0
        self.files_disk_only = 0
        self.files_ird_only = 0
        self.files_size_mismatch = 0
        self.files_hash_mismatch = 0

        self.dirs_ok = 0
        self.dirs_disk = 0
        self.dirs_ird = 0
        self.dirs_disk_only = 0
        self.dirs_ird_only = 0

        self.dir_file_mismatch = 0

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

    def md5sum(self, filename):
        with open(filename, mode='rb') as f:
            d = hashlib.md5()
            for buf in iter(partial(f.read, 4096), b''):
                d.update(buf)
        return d.hexdigest()

    def _check(self, path, files, ird_files):
        # first, add all disk files and set on_disk attribute
        merged = files
        for file in merged:
            file['in_ird'] = False
            file['on_disk'] = True
            file['ird_content'] = []
            if 'content' not in file:
                file['content'] = []
                self.files_disk += 1
            else:
                self.dirs_disk += 1

        # now, check every ird file and either merge or add to merged
        for irdfile in ird_files:
            elem = next((x for x in merged if x['name'] == irdfile['name']), None)
            if elem is None: # not in merged yet
                irdfile['in_ird'] = True
                irdfile['on_disk'] = False
                irdfile['ird_size'] = irdfile['size']
                irdfile['ird_hash'] = irdfile['hash']
                del irdfile['size']
                del irdfile['hash']
                if 'content' in irdfile:
                    irdfile['ird_content'] = irdfile['content']
                    del irdfile['content']
                    self.dirs_ird += 1
                else:
                    irdfile['ird_content'] = []
                    self.files_ird += 1
                merged += [irdfile]
            else: # already known -> compare
                elem['in_ird'] = True
                elem['ird_size'] = irdfile['size']
                elem['ird_hash'] = irdfile['hash']
                if 'content' in irdfile:
                    elem['ird_content'] = irdfile['content']
                    self.dirs_ird += 1
                else:
                    elem['ird_content'] = []
                    self.files_ird += 1

        # check every file
        for file in merged:
            filepath = os.path.join(path, file['name'])
            if file['on_disk'] and not file['in_ird']:
                print(f"{filepath} not in IRD")
                if 'content' in file:
                    self.dirs_disk_only += 1
                else:
                    self.files_disk_only += 1
            elif not file['on_disk'] and file['in_ird']:
                print(f"{filepath} not on disk")
                if 'content' in file:
                    self.dirs_ird_only += 1
                else:
                    self.files_ird_only += 1
            elif len(file['content']) == 0 != len(file['ird_content']) == 0:
                print(f"{filepath} is file and should be dir or vice versa")
                self.dir_file_mismatch += 1
            elif len(file['content']) == 0: # check file size + hash
                if file['size'] != file['ird_size']:
                    print(f"Size mismatch in {filepath}: {file['size']} on disk, {file['ird_size']} in IRD")
                    self.files_size_mismatch += 1
                else:
                    file['hash'] = self.md5sum(filepath)
                    if file['hash'] != file['hash']:
                        print(f"Hash mismatch in {filepath}: {file['hash']} on disk, {file['ird_hash']} in IRD")
                        self.files_hash_mismatch += 1
                    else:
                        print("File ok: "+filepath)
                        self.files_ok += 1
            else:
                self.dirs_ok += 1
            if len(file['content']) > 0:
                self._check(f"{filepath}/", file['content'], file['ird_content'])

    def check(self, ird):
        self._check(self.dir, self.files, ird.files)

        print(f"Dirs on disk:             {self.dirs_disk}")
        print(f"Dirs in ird:              {self.dirs_ird}")
        print(f"Dirs ok:                  {self.dirs_ok}")
        print(f"Disk dirs not in IRD:     {self.dirs_disk_only}")
        print(f"IRD dirs not on disk:     {self.dirs_ird_only}")
        print(f"File/Dir type mismatch:   {self.dir_file_mismatch}")

        print(f"Files on disk:            {self.files_disk}")
        print(f"Files in ird:             {self.files_ird}")
        print(f"Files ok:                 {self.files_ok}")
        print(f"Disk files not in IRD:    {self.files_disk_only}")
        print(f"IRD files not on disk:    {self.files_ird_only}")
        print(f"Files with size mismatch: {self.files_size_mismatch}")
        print(f"Files with hash mismatch: {self.files_hash_mismatch}")

        if self.files_disk != self.files_ird or self.files_disk_only+self.files_ird_only+self.files_size_mismatch+self.files_hash_mismatch > 0:
            print("GAME DATA INVALID")
        else:
            print("GAME DATA VALID")

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

    if args.action == 'print':
        ird.print_header()
        ird.print_files()
    elif args.action == 'md5sum':
        ird.print_md5sum()
    elif args.action == 'check':
        ird.print_header()
        game = GameDir(args.game_dir)
        game.check(ird)
