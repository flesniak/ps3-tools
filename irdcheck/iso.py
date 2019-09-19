#!/usr/bin/env python3

import construct as c

IsoSectorSize = 2048

# DString = c.NullTerminated(c.GreedyString("ascii"), term=b"\x20")
UtfDString = lambda len: c.FocusedSeq("str", "str"/c.PaddedString(len-1, "ascii"), "val"/c.Int8ul)

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
    c.StopIf(c.this._.type == 0xff),
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
    "identifier" / TagIdentifier,
    "version" / c.Int16ul,
    "checksum" / c.Int8ul,
    c.Padding(1),
    "serial_number" / c.Int16ul,
    "descriptor_crc" / c.Int16ul,
    "descriptor_crc_length" / c.Int16ul,
    "sector" / c.Int32ul
)

DomainIDSuffix = c.Struct(
    "udf_revision" / c.Int16ul,
    "domain_flags" / c.Int8ul,
    c.Padding(5)
)

ImplementationIDSuffix = c.Struct(
    "os_class" / c.Int8ul,
    "os_identifier" / c.Int8ul,
    c.Padding(6)
)

UDFIDSuffix = c.Struct(
    "udf_revision" / c.Int16ul,
    "os_class" / c.Int8ul,
    "os_identifier" / c.Int8ul,
    c.Padding(4)
)

EntityIDHeader = c.Struct(
    "flags" / c.Int8ul,
    "identifier" / c.PaddedString(23, "ascii")
)

DomainEntityID = c.Struct(
    c.Embedded(EntityIDHeader),
    "suffix" / DomainIDSuffix
)

ImplementationEntityID = c.Struct(
    c.Embedded(EntityIDHeader),
    "suffix" / ImplementationIDSuffix
)

UDFEntityID = c.Struct(
    c.Embedded(EntityIDHeader),
    "suffix" / UDFIDSuffix
)

PartitionMap = c.Struct(
    "type" / c.Int8ul,
    "length" / c.Int8ul,
    "type_id" / c.If(c.this.type == 2,
        c.FocusedSeq("a", c.Padding(2), "a"/UDFEntityID)),
    "volume_sequence_number" / c.Int16ul,
    "partition_number" / c.Int16ul,
    c.If(c.this.type == 2, c.Padding(24))
)

LongAllocationDescriptor = c.Struct(
    "length" / c.Int32ul,
    "sector" / c.Int32ul,
    "partition" / c.Int16ul,
    c.Padding(6)
)

OSTACharset = c.Struct(
    "type" / c.Int8ul, #c.Const(0, ),
    "name" / c.PaddedString(63, "ascii") #c.Const("OSTA Compressed Unicode", )
)

Timestamp = c.Struct(
    "type_and_timezone" / c.Int16ul,
    "year" / c.Int16ul,
    "month" / c.Int8ul,
    "day" / c.Int8ul,
    "hour" / c.Int8ul,
    "minute" / c.Int8ul,
    "second" / c.Int8ul,
    "centisecs" / c.Int8ul,
    "hundred_us" / c.Int8ul,
    "us" / c.Int8ul
)

FileSetDescriptor = c.Struct(
    "recording_timestamp" / Timestamp,
    "interchange_level" / c.Int16ul,
    "max_interchange_level" / c.Int16ul,
    "charset_list" / c.Int32ul,
    "max_charset_list" / c.Int32ul,
    "fileset_number" / c.Int32ul,
    "fileset_desc_number" / c.Int32ul,
    "logical_volume_identifier_charset" / OSTACharset,
    "logical_volume_identifier" / UtfDString(128),
    "fileset_identifier_charset" / OSTACharset,
    "fileset_identifier" / UtfDString(32),
    "copyright_identifier" / UtfDString(32),
    "abstract_identifier" / UtfDString(32),
    "root_directory" / LongAllocationDescriptor,
    "domain_identifier" / DomainEntityID,
    "next_extent" / LongAllocationDescriptor,
    "stream_directory" / LongAllocationDescriptor,
    c.Padding(32)
)

LogicalVolumeDescriptor = c.Struct(
    "volume_sequence_number" / c.Int32ul,
    "character_set" / OSTACharset,
    "volume_identifier" / UtfDString(128),
    "logical_block_size" / c.Int32ul,
    "domain_identifier" / DomainEntityID,
    "content" / LongAllocationDescriptor, # file set descriptor location
    "map_table_length" / c.Int32ul,
    "partition_map_count" / c.Int32ul,
    "implementation_identifier" / ImplementationEntityID,
    "implementation_data" / c.Bytes(128),
    "integrity_sequence_extent" / c.Bytes(8),
    "partition_maps" / c.Array(c.this.partition_map_count, PartitionMap)
)

UdfVolumeDescriptor = c.Padded(2048, c.Struct(
    # "start" / c.Tell,
    "tag" / DescriptorTag,
    "desc" / c.Switch(c.this.tag.identifier, {
        "logical_volume_descriptor": LogicalVolumeDescriptor,
        "file_set_descriptor": FileSetDescriptor,
    }, default=c.Pass),
    # "end" / c.Tell
))

# UdfVolumeDescriptorSequence = c.Array(5, UdfVolumeDescriptor)
UdfVolumeDescriptorSequence = c.GreedyRange(c.FocusedSeq("e",
    "e" / UdfVolumeDescriptor,
    c.StopIf(lambda ctx: ctx.e.tag.identifier == "terminating_descriptor"))
)

AnchorVolumeDescriptor = c.Struct(
    "descriptor_tag" / DescriptorTag,
    "main_volume_descriptor_length" / c.Int32ul,
    "main_volume_descriptor_sector" / c.Int32ul,
    "backup_volume_descriptor_length" / c.Int32ul,
    "backup_volume_descriptor_sector" / c.Int32ul,
    c.Seek(c.this.main_volume_descriptor_sector * IsoSectorSize),
    "seekedto" / c.Tell,
    "descriptors" / UdfVolumeDescriptorSequence
)

VolumeDescriptor = c.Struct(
    "type" / c.Int8ul,
    "identifier" / c.PaddedString(5, "ascii"),
    "version" / c.Int8ul,
    c.Padding(1),
    "payload" / c.Switch(c.this.identifier, {
        "CD001": PrimaryVolumeDescriptor,
        "NSR02": c.Pointer(0x100 * IsoSectorSize, AnchorVolumeDescriptor),
        "NSR03": c.Pointer(0x100 * IsoSectorSize, AnchorVolumeDescriptor),
        "BEA01": c.Pass,
        "BOOT2": c.Pass,
        "TEA01": c.Pass
    })
)

VolumeDescriptorSequence = c.GreedyRange(c.FocusedSeq("vd",
   "vd" / c.Padded(IsoSectorSize, VolumeDescriptor),
   c.StopIf(lambda ctx: ctx.vd.identifier == "TEA01"))
)

IsoFile = c.Struct(
    "vds" / c.Pointer(0x10 * IsoSectorSize, VolumeDescriptorSequence),
    # "path_table" / c.Pointer(c.this.vds[0].payload.lpath_table_sector * IsoSectorSize,
    #    c.FixedSized(c.this.vds[0].payload.path_table_size, PathTable)),
    #"directory_table" / c.Pointer(c.this.pvd.root.data_sector * IsoSectorSize, DirectoryTable),
)
