#!/usr/bin/env python3

import gzip
import sys
import os
import io
from construct.core import ConstError

import ird
import iso

class IrdFile:
    def __init__(self, filename):
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

    def _print_files(self, files, prefix):
      for e in files:
        line = prefix+e['name']
        if not 'content' in e:
            line += f" | {e['size']}"
        if 'md5' in e:
            line += f" | {e['md5']}"
        if 'start_sector' in e:
            line += f" | {e['start_sector']}"
        print(line)
        if 'content' in e:
          self._print_files(e['content'], f"{prefix}{e['name']}/")

    def print_files(self):
        self._print_files(self.files, '/')

    def map_md5sums(self, dir):
        for file in dir:
            if 'content' in file: # recurse directories
                self.map_md5sums(file['content'])
            else:
                for ird_file in self.content.files:
                    key = file['start_sector']
                    if key == ird_file.key:
                        file['md5'] = ird_file.hash
                        break
                # if 'md5' not in file:
                print(f"File {key} not found in UDF header")

    def id(self):
        return self.content.game_id

    def name(self):
        return self.content.game_name

if __name__ == "__main__":
    ird = IrdFile(sys.argv[1])
    # for f in ird.content.files:
    #     print(f"{f.key}  {f.hash.hex()}")
    # print(ird.content)
    # print(len(ird.content.files))
    print(ird.files)
    # ird.print_files()

    # with open("header.bin", "wb") as f:
    #     f.write(ird.content.header)
    # with open("footer.bin", "wb") as f:
    #     f.write(ird.content.footer)
