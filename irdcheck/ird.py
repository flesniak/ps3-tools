#!/usr/bin/env python3

from construct import Struct, Int8ul, PaddedString, Const, PascalString, Int32ul, Compressed, GreedyBytes, Prefixed, PrefixedArray, Bytes, Int64ul, Padding, Int16ul, Int16ub, Int32ub, Tell, Pointer

IrdMagic = Const("3IRD", PaddedString(4, encoding="ascii"))

Md5Sum = Bytes(16)

IrdFile = Struct(
    "sector" / Int64ul,
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
