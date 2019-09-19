#!/usr/bin/env python3

import construct as c

IsoSectorSize = 2048

# DString = c.NullTerminated(c.GreedyString("ascii"), term=b"\x20")

Filename = lambda len: c.ExprAdapter(c.PaddedString(len, "ascii"),
    lambda o,c: o[:-2] if o.endswith(";1") else o,
    lambda o,c: o+";1")

Dirname = lambda len: c.ExprAdapter(c.PaddedString(len, "ascii"),
    lambda o,c: "." if o=="" else ".." if o=="\x01" else o,
    lambda o,c: o) # TODO

PathTableEntry = c.Struct(
    "length" / c.Int8ul,
    "extended_attr_length" / c.Int8ul,
    "extent_sector" / c.Int32ul,
    "parent_dir_number" / c.Int16ub,
    "dirname" / c.PaddedString(c.this.length, "ascii"),
    c.Padding(c.this.length%2)
)

PathTable = c.Struct(
    "root" / PathTableEntry,
    "entries" / c.GreedyRange(PathTableEntry)
)

DirectoryRecordDate = c.Struct(
    "year" / c.ExprAdapter(c.Int8ul, lambda o,c: o+1900, lambda o,c: o-1900),
    "month" / c.Int8ul,
    "day" / c.Int8ul,
    "hour" / c.Int8ul,
    "minute" / c.Int8ul,
    "second" / c.Int8ul,
    "gmt_offset" / c.Int8ul
)

DirectoryRecordFlags = c.BitStruct(
    "followup_record" / c.Flag,
    c.Padding(2),
    "perms_exattrs" / c.Flag,
    "has_exattrs" / c.Flag,
    "associated" / c.Flag,
    "directory" / c.Flag,
    "hidden" / c.Flag,
)

DirectoryRecord = c.Struct(
    "length" / c.Int8ul,
    "extended_attr_length" / c.Int8ul,
    "data_sector" / c.Int32ul,
    "data_sector_be" / c.Int32ub,
    "data_length" / c.Int32ul,
    "data_length_be" / c.Int32ub,
    "date" / DirectoryRecordDate,
    "flags" / DirectoryRecordFlags,
    "interleave_unit_size" / c.Int8ul,
    "interleave_gap" / c.Int8ul,
    "vol_sequence_number" / c.Int16ul,
    "vol_sequence_number_be" / c.Int16ub,
    "name_length" / c.Int8ul,
    "name" / c.IfThenElse(c.this.flags.directory,
        Dirname(c.this.name_length),
        Filename(c.this.name_length)),
    c.Padding(c.this.length-c.this.name_length-33),
    "linkdir" / c.Computed(lambda ctx: ctx.name in [".", ".."]),
    "content" / c.If(lambda ctx: ctx.flags.directory and not ctx.linkdir,
        c.Pointer(c.this.data_sector * IsoSectorSize,
        c.LazyBound(lambda: DirectoryTable)))
)

DirectoryTable = c.GreedyRange(c.FocusedSeq("e",
    "e" / DirectoryRecord,
    c.StopIf(c.this.e.length == 0))
)

PrimaryVolumeDescriptor = c.Struct(
    "type" / c.Const(0x1, c.Int8ul),
    "std_identifier" / c.Const("CD001", c.PaddedString(5, "ascii")),
    "std_version" / c.Int8ul,
    c.Padding(1),
    "sys_identifier" / c.PaddedString(32, "ascii"),
    "vol_identifier" / c.PaddedString(32, "ascii"),
    c.Padding(8),
    "vol_space_size" / c.Int32ul,
    "vol_space_size_be" / c.Int32ub,
    c.Padding(32),
    "vol_set_size" / c.Int16ul,
    "vol_set_size_be" / c.Int16ub,
    "vol_sequence_number" / c.Int16ul,
    "vol_sequence_number_be" / c.Int16ub,
    "logical_block_size" / c.Const(IsoSectorSize, c.Int16ul),
    "logical_block_size_be" / c.Const(IsoSectorSize, c.Int16ub),
    "path_table_size" / c.Int32ul,
    "path_table_size_be" / c.Int32ub,
    "lpath_table_sector" / c.Int32ul,
    "opt_lpath_table_sector" / c.Int32ul,
    "mpath_table_sector_be" / c.Int32ub,
    "opt_mpath_table_sector_be" / c.Int32ub,
    "root" / DirectoryRecord,
    "vol_set_identifier" / c.PaddedString(128, "ascii"),
    "publisher_identifier" / c.PaddedString(128, "ascii"),
    "data_preparer_identifier" / c.PaddedString(128, "ascii"),
    "application_identifier" / c.PaddedString(128, "ascii"),
    "copyright_file_identifier" / c.PaddedString(38, "ascii"),
    "abstract_file_identifier" / c.PaddedString(36, "ascii"),
    "bibliographic_file_identifier" / c.PaddedString(37, "ascii"),
    "vol_creation_date" / c.PaddedString(17, "ascii"),
    "vol_modification_date" / c.PaddedString(17, "ascii"),
    "vol_expiration_date" / c.PaddedString(17, "ascii"),
    "vol_effective_date" / c.PaddedString(17, "ascii"),
    "file_structure_version" / c.Int8ul,
    c.Padding(1166)
)

VolumeDescriptorSequence = c.GreedyRange(c.FocusedSeq("e",
    "e" / VolumeDescriptor,
    c.StopIf(c.this.e.descriptor_tag.tag_identifier == "terminating_descriptor"))
)

TagIdentifier = c.Enum(c.Int16ul,
    primary_volume_descriptor = 0x0001,
    anchor_volume_descriptor_pointer = 0x0002,
    volume_descriptor_pointer = 0x0003,
    implementation_use_volume_descriptor = 0x0004,
    partition_descriptor = 0x0005,
    logical_volume_descriptor = 0x0006,
    unallocated_space_descriptor = 0x0007,
    terminating_descriptor = 0x0008,
    logical_volume_integrity_descriptor = 0x0009,
    file_set_descriptor = 0x0100,
    file_identifier_descriptor = 0x0101,
    allocation_extent_descriptor = 0x0102,
    indirect_entry = 0x0103,
    terminal_entry = 0x0104,
    file_entry = 0x0105,
    extended_attribute_header_descriptor = 0x0106,
    unallocated_space_entry = 0x0107,
    space_bitmap_descriptor = 0x0108,
    partition_integrity_entry = 0x0109,
    extended_file_entry = 0x010a
)

DescriptorTag = c.Struct(
    "tag_identifier" / TagIdentifier,
    "descriptor_version" / c.Int16ul,
    "checksum" / c.Int8ul,
    Padding(1),
    "serial_number" / c.Int16ul,
    "descriptor_crc" / c.Int16ul,
    "descriptor_crc_length" / c.Int16ul,
    "tag_location" / c.Int32ul
)

AnchorVolumeDescriptor = c.Struct(
    "descriptor_tag" / DescriptorTag,
    "main_volume_descriptor_length" / c.Int32ul,
    "main_volume_descriptor_sector" / c.Int32ul,
    "backup_volume_descriptor_length" / c.Int32ul,
    "backup_volume_descriptor_sector" / c.Int32ul
)

IsoFile = c.Struct(
    "pvd" / c.Pointer(0x10*IsoSectorSize, PrimaryVolumeDescriptor),
    "path_table" / c.Pointer(c.this.pvd.lpath_table_sector*IsoSectorSize,
        c.FixedSized(c.this.pvd.path_table_size, PathTable)),
    "directory_table" / c.Pointer(c.this.pvd.root.data_sector * IsoSectorSize, DirectoryTable),
)
