#!/usr/bin/env python3

import gzip
import sys
import os
# from pycdlib import pycdlib
from io import BytesIO
from construct import Struct, Int8ul, PaddedString, Const, PascalString, Int32ul, Compressed, GreedyBytes, Prefixed, PrefixedArray, Bytes, Int64ul, Padding, Int16ul, Int16ub, Int32ub, Tell, Pointer
from construct.core import ConstError

IrdMagic = Const("3IRD", PaddedString(4, encoding="ascii"))
Md5Sum = Bytes(16)
IrdFile = Struct(
    "key" / Int64ul,
    "hash" / Md5Sum
)
IrdBase = Struct(
    "magic" / IrdMagic,
    "version" / Int8ul,
    "game_id" / PaddedString(9, "ascii"),
    "game_name" / PascalString(Int8ul, "utf-8"),
    "update_version" / PaddedString(4, "ascii"),
    "game_version" / PaddedString(5, "ascii"),
    "app_version" / PaddedString(5, "ascii"),
    "header" / Prefixed(Int32ul, Compressed(GreedyBytes, "gzip")),
    "footer" / Prefixed(Int32ul, Compressed(GreedyBytes, "gzip")),
    "regions" / PrefixedArray(Int8ul, Md5Sum),
    "files" / PrefixedArray(Int32ul, IrdFile)
)

#udf sector size 2048
#first anchor point at sector 256

IsoSectorSize = 2048

PrimaryVolumeDescriptor = Struct(
    "type" / Const(0x1, Int8ul),
    "std_identifier" / Const("CD001", PaddedString(32, "ascii")),
    "std_version" / Int8ul,
    Padding(1),
    "sys_identifier" / PaddedString(32, "ascii"),
    "vol_identifier" / PaddedString(32, "ascii"),
    Padding(8),
    "vol_space_size" / Int32ul,
    "vol_space_size_be" / Int32ub,
    Padding(32),
    "vol_set_size" / Int16ul,
    "vol_set_size_be" / Int16ub,
    "vol_sequence_number" / Int16ul,
    "vol_sequence_number_be" / Int16ub,
    "logical_block_size" / Int16ul,
    "logical_block_size_be" / Int16ub,
    "path_table_size" / Int32ul,
    "path_table_size_be" / Int32ub,
    "lpath_table_sector" / Int32ul,
    "opt_lpath_table_sector" / Int32ul,
    "mpath_table_sector_be" / Int32ub,
    "opt_mpath_table_sector_be" / Int32ub,
    "root_directory" / PaddedString(34, "ascii"),
    "vol_set_identifier" / PaddedString(128, "ascii"),
    "publisher_identifier" / PaddedString(128, "ascii"),
    "data_preparer_identifier" / PaddedString(128, "ascii"),
    "application_identifier" / PaddedString(128, "ascii"),
    "copyright_file_identifier" / PaddedString(38, "ascii"),
    "abstract_file_identifier" / PaddedString(36, "ascii"),
    "bibliographic_file_identifier" / PaddedString(37, "ascii"),
    "vol_creation_date" / PaddedString(17, "ascii"),
    "vol_modification_date" / PaddedString(17, "ascii"),
    "vol_expiration_date" / PaddedString(17, "ascii"),
    "vol_effective_date" / PaddedString(17, "ascii"),
    "file_structure_version" / Int8ul,
    Padding(1),
    Padding(512),
    Padding(653),
    "end" / Tell
)

IsoFile = Struct(
    "pvd" / Pointer(0x10*IsoSectorSize, PrimaryVolumeDescriptor)
)

#
# IsoBase = Struct(
#     "pvd" / PrimaryVolumeDescriptor,
# )

# class UdfIO(object):
#     def __init__(self, header, footer):
#         self.data = header+footer
#         self.sizepoint=0
#         self.sizeoffset=2048*6
#         self.virtual_size = len(self.data)
#
#     def read(self,size=-1):
#         print(f'read at {self.sizepoint} for {size} bytes')
#         print(str(self.data[self.sizepoint:self.sizepoint+32]))
#         self.sizepoint+=size
#         return self.data[self.sizepoint:self.sizepoint+size]
#
#     def tell(self):
#         return self.sizepoint
#
#     def seek(self, lok, rel=os.SEEK_SET):
#         if rel == os.SEEK_SET:
#             self.sizepoint=lok
#         elif rel == os.SEEK_CUR:
#             self.sizepoint+=lok
#         else:
#             self.sizepoint=lok
#         print(f'seek {lok} {rel}')
#         return self.sizepoint


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
            IrdMagic.parse(magic_bytes) # fails if incorrect magic
        except ConstError as e:
            raise Exception(f"Incorrect magic bytes: {e}") from None

        self.content = IrdBase.parse_stream(handle)

        self.parse_header()

    def parse_header(self):
        # hdr = UdfIO(self.content.header, self.content.footer)
        # #hdr = BytesIO(self.content.header)
        # iso = pycdlib.PyCdlib()
        # iso.open_fp(hdr)
        self.header_parsed = IsoFile.parse(self.content.header)

    def id(self):
        return self.content.game_id

    def name(self):
        return self.content.game_name

if __name__ == "__main__":
    ird = IrdFile(sys.argv[1])
    # print(ird.content)
    # print(len(ird.content.files))
    print(ird.header_parsed)

    # with open("header.bin", "wb") as f:
    #     f.write(ird.content.header)
    # with open("footer.bin", "wb") as f:
    #     f.write(ird.content.footer)
