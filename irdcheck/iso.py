#!/usr/bin/env python3

import construct as c

IsoSectorSize = 2048

# DString = c.NullTerminated(c.GreedyString("ascii"), term=b"\x20")
UtfDString = lambda len: c.FocusedSeq("str", "str"/c.PaddedString(len-1, "ascii"), "val"/c.Int8ul)
OSTACompressedUnicode = lambda len: c.FocusedSeq("str", "compression_id" / c.Int8ul,
    "str" / c.IfThenElse(
        c.this.compression_id == 16,
        c.PaddedString(len-1, "utf16"),
        c.PaddedString(len-1, "utf8"),
    ))

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

ApplicationIDSuffix = c.Struct(
    "implementation_use" / c.Bytes(8)
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

ApplicationEntityID = c.Struct(
    c.Embedded(EntityIDHeader),
    "suffix" / ApplicationIDSuffix
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

ShortAD = c.Struct(
    "length" / c.Int32ul,
    "sector" / c.Int32ul,
)

LBAddr = c.Struct(
    "sector" / c.Int32ul,
    "partition" / c.Int16ul,
)

LongAD = c.Struct(
    "length" / c.Int32ul,
    c.Embedded(LBAddr),
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
    "root_directory_ad" / LongAD,
    "domain_identifier" / DomainEntityID,
    "next_extent" / LongAD,
    "stream_directory" / LongAD,
    c.Padding(32),
    # "root_directory" / c.LazyBound(lambda: PartitionDirectory(
    #     c.this._._._.partition_start, c.this._.root_directory_ad.sector))
)

LogicalVolumeDescriptor = c.Struct(
    "volume_sequence_number" / c.Int32ul,
    "character_set" / OSTACharset,
    "volume_identifier" / UtfDString(128), # TODO: should be OSTACompressedUnicode?
    "logical_block_size" / c.Const(IsoSectorSize, c.Int32ul),
    "domain_identifier" / DomainEntityID,
    "content" / LongAD, # file set descriptor sequnce location
    "map_table_length" / c.Int32ul,
    "partition_map_count" / c.Int32ul,
    "implementation_identifier" / ImplementationEntityID,
    "implementation_use" / c.Bytes(128),
    "integrity_sequence_extent" / c.Bytes(8),
    "partition_maps" / c.Array(c.this.partition_map_count, PartitionMap)
)

FileCharacteristics = c.BitStruct(
    c.Padding(3),
    "metadata" / c.Flag,
    "parent" / c.Flag,
    "deleted" / c.Flag,
    "directory" / c.Flag,
    "existence_hidden" / c.Flag,
)

FileIdentifierDescriptor = c.Aligned(4, c.Struct(
    "version" / c.Int16ul,
    "characteristics" / FileCharacteristics,
    "identifier_length" / c.Int8ul,
    "icb" / LongAD,
    "implementation_use_length" / c.Int16ul,
    "implementation_use" / c.Bytes(c.this.implementation_use_length),
    "identifier" / c.If(c.this.identifier_length > 0,
        OSTACompressedUnicode(c.this._.identifier_length)),
    # c.StopIf(lambda ctx: ctx.identifier != "PS3_UPDATE"),
    # "entries" / c.If(c.this.characteristics.directory == True,
    #     c.LazyBound(lambda: PartitionDirectory(c.this._._._._._._.partition_start,
    #         c.this._.icb.sector)))
))

ICBTag = c.Struct(
    "prior_entries" / c.Int32ul,
    "strategy_type" / c.Int16ul,
    "strategy_param" / c.Int16ul,
    "max_entries" / c.Int16ul,
    c.Padding(1),
    "file_type" / c.Int8ul,
    "parent_icb" / LBAddr,
    "flags" / c.Int16ul
)

FileEntry = c.Struct(
    "icb" / ICBTag,
    "uid" / c.Int32ul,
    "gid" / c.Int32ul,
    "permissions" / c.Int32ul,
    "link_count" / c.Int16ul,
    "record_fmt" / c.Const(0, c.Int8ul),
    "record_display_attrs" / c.Const(0, c.Int8ul),
    "record_length" / c.Const(0, c.Int32ul),
    "information_length" / c.Int64ul,
    "logical_blocks_recorded" / c.Int64ul,
    "access_time" / Timestamp,
    "modification_time" / Timestamp,
    "attribute_time" / Timestamp,
    "checkpoint" / c.Const(1, c.Int32ul),
    "extended_attr_icb" / LongAD,
    "implementation_identifier" / ImplementationEntityID,
    "unique_id" / c.Int64ul,
    "extended_attrs_length" / c.Int32ul,
    "allocation_descriptors_length" / c.Int32ul,
    "extended_attrs" / c.Bytes(c.this.extended_attrs_length),
    "allocation_descriptors" / c.Array(c.this.allocation_descriptors_length//8,
        ShortAD
        # c.Struct(
        #     "ad" / ShortAD,
        #     "files" / c.Pointer(
        #         c.this._._._.partition_start + c.this.ad.sector * IsoSectorSize,
        #         c.LazyBound(lambda: UdfDescriptorSequence)
        #         # c.FixedSized(c.this.ad.length, c.LazyBound(lambda: c.Array(4, UdfDescriptor)))
        #         # c.FixedSized(c.this.ad.length, c.LazyBound(lambda: c.GreedyRange(UdfDescriptor)))
        #         # todo: replace greedyrange with fixed range
        #     )
        # )
    ),
)

AllocationExtentDescriptor = c.Struct(
    "previous_location" / c.Int32ul,
    "descriptors_length" / c.Int32ul,
)

AccessType = c.Enum(c.Int32ul,
    unspecified=1,
    read_only=2,
    rewritable=3,
    overwritable=4,
)

PartitionDescriptor = c.Struct(
    "volume_sequence_number" / c.Int32ul,
    "flags" / c.Int16ul,
    "number" / c.Int16ul,
    "content_id" / ApplicationEntityID,
    "content_use" / c.Bytes(128),
    "access_type" / AccessType,
    "partition_start" / c.Int32ul,
    "partition_length" / c.Int32ul,
    "implementation_identifier" / ImplementationEntityID,
    "implementation_use" / c.Bytes(128),
    c.Padding(156),
)

PartitionHeader = c.Struct(
    "unallocated_space_table" / ShortAD,
    "unallocated_space_bitmap" / ShortAD,
    "partition_integrity_table" / ShortAD,
    "free_space_table" / ShortAD,
    "free_space_bitmap" / ShortAD,
    c.Padding(88)
)

UdfDescriptor = c.Struct(
    "start" / c.Tell,
    "tag" / DescriptorTag,
    # c.StopIf(lambda ctx: ctx.tag.identifier == "terminating_descriptor" or ctx.tag.identifier == 0),
    # "tag" / c.ExprValidator(DescriptorTag, lambda o,ctx: o.identifier != 0 and o.identifier != "terminating_descriptor"), # abort parsing on terminator or zero identifier
    "desc" / c.Switch(c.this.tag.identifier, {
        "logical_volume_descriptor": LogicalVolumeDescriptor,
        "file_set_descriptor": FileSetDescriptor,
        "partition_descriptor": PartitionDescriptor,
        "file_entry": FileEntry,
        "allocation_extent_descriptor": AllocationExtentDescriptor,
        "file_identifier_descriptor": FileIdentifierDescriptor,
    }, default=c.Pass),
    # "end" / c.Tell
)

# UdfDescriptorSequence = c.GreedyRange(UdfDescriptor)
UdfDescriptorSequence = c.RepeatUntil(
    lambda x,lst,ctx: x.tag.identifier == "terminating_descriptor" or x.tag.identifier == 0,
    UdfDescriptor
)
# UdfDescriptorSequence = c.GreedyRange(c.FocusedSeq("e",
#     "e" / UdfDescriptor,
#     c.StopIf(lambda ctx: ctx.e.tag.identifier == "terminating_descriptor"))
# )

PaddedUdfDescriptor = c.Padded(2048, UdfDescriptor)

# PaddedUdfDescriptorSequence = c.GreedyRange(c.FocusedSeq("e",
#     "e" / PaddedUdfDescriptor,
#     c.StopIf(lambda ctx: ctx.e.tag.identifier == "terminating_descriptor" or ctx.e.tag.identifier == 0))
# )
# PaddedUdfDescriptorSequence = c.Array(5, PaddedUdfDescriptor)
PaddedUdfDescriptorSequence = c.RepeatUntil(
    lambda x,lst,ctx: x.tag.identifier == "terminating_descriptor" or x.tag.identifier == 0,
    PaddedUdfDescriptor
)

PartitionDirectory = lambda partition_start, sector_offset: c.FocusedSeq("file_entries",
    # c.Seek(partition_start + sector_offset * IsoSectorSize),
    c.Seek((partition_start + sector_offset) * IsoSectorSize),
    # "partition_start" / c.Computed(partition_start),
    # "loc" / c.Tell,
    # "file_entry" / PaddedUdfDescriptor,
    # "file_entry" / c.UdfDescriptor,
    "file_entries" / UdfDescriptorSequence
)

Partition = c.Struct(
    c.Padding(32 * IsoSectorSize), # quirk to skip first strange file entry descriptor
    "partition_start" / c.Tell,
    "fileset" / UdfDescriptor,
)

PartitionStart = lambda start_sector, fileset_sector: c.FocusedSeq("file_set",
    c.Seek((start_sector + fileset_sector) * IsoSectorSize),
    "file_set" / UdfDescriptor,
)

AnchorVolumeDescriptor = c.Struct(
    "descriptor_tag" / DescriptorTag,
    "main_volume_descriptor_length" / c.Int32ul,
    "main_volume_descriptor_sector" / c.Int32ul,
    "backup_volume_descriptor_length" / c.Int32ul,
    "backup_volume_descriptor_sector" / c.Int32ul,
    c.Seek(c.this.main_volume_descriptor_sector * IsoSectorSize),
    "descriptors" / PaddedUdfDescriptorSequence,
    #"partition" / c.Pointer(c.this.descriptors[2].desc.partition_start * IsoSectorSize, FileEntry),
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

# VolumeDescriptorSequence = c.GreedyRange(c.FocusedSeq("vd",
#    "vd" / c.Padded(IsoSectorSize, VolumeDescriptor),
#    c.StopIf(lambda ctx: ctx.vd.identifier == "TEA01"))
# )
VolumeDescriptorSequence = c.RepeatUntil(
    lambda x,lst,ctx: x.identifier == "TEA01",
    c.Padded(IsoSectorSize, VolumeDescriptor)
)

IsoVolumeDescriptors = c.Pointer(0x10 * IsoSectorSize, VolumeDescriptorSequence)

IsoFile = c.Struct(
    "vds" / c.Pointer(0x10 * IsoSectorSize, VolumeDescriptorSequence),
    # "path_table" / c.Pointer(c.this.vds[0].payload.lpath_table_sector * IsoSectorSize,
    #    c.FixedSized(c.this.vds[0].payload.path_table_size, PathTable)),
    #"directory_table" / c.Pointer(c.this.pvd.root.data_sector * IsoSectorSize, DirectoryTable),
    # "partition" / c.Pointer(c.this.vds[4].payload.descriptors[2].desc.partition_start * IsoSectorSize, FileEntry),
    #"partition" / c.Pointer(c.this.vds[4].payload.descriptors[2].desc.partition_start * IsoSectorSize, PartitionHeader),
    "partition" / c.Pointer(c.this.vds[4].payload.descriptors[2].desc.partition_start * IsoSectorSize, Partition),
    #"fileset" / c.Pointer(480 * IsoSectorSize, PaddedUdfDescriptor),
)

def ParseUdfDirectory(fd, partition_start, entry_sector):
    entry = PartitionStart(partition_start, entry_sector).parse_stream(fd)
    if len(entry.desc.allocation_descriptors) != 0:
        print(f"Number of allocation descriptors unsupported: {entry.desc.allocation_descriptors}")
    dir_sector = entry.desc.allocation_descriptors[0].sector
    dirtree = []
    dir = PartitionDirectory(partition_start, dir_sector).parse_stream(fd)
    for entry in dir:
        print(f"parse dir entry {entry}")
        if (entry.tag.identifier == 0): # abort on last empty file identifier descriptor
            break
        if entry.desc.characteristics.parent == True: # skip parent link entries
            continue
        elem = {
            "name": entry.desc.identifier,
            "size": entry.desc.icb.length
        }
        if entry.desc.characteristics.directory == True:
            print(f"entering directory {entry.desc.identifier}")
            elem["content"] = ParseUdfDirectory(fd, partition_start, entry.desc.icb.sector)
        dirtree += [elem]

    print(dir)

def ParseUdfPartition(fd, partition_start, fileset_sector):
    partition_start += 32 # quirk to skip strange file entry descriptors
    fileset = PartitionStart(partition_start, fileset_sector).parse_stream(fd)
    # print(fileset)
    # root = PartitionDirectory(partition_start,
    #   fileset.desc.root_directory_ad.sector).parse_stream(fd)
    # if (len(root) > 1):
    #     print("Warning: more than one file entry in root directory")
    # # print(root)
    # dirtree = []
    # for ad in root[0].desc.allocation_descriptors:
    #     dirtree += ParseUdfDirectory(fd, partition_start, ad.sector)
    # return dirtree
    return ParseUdfDirectory(fd, partition_start, fileset.desc.root_directory_ad.sector)

def ParseUdf(fd, anchor_desc):
    fileset_sector = None
    partition_start = None
    for desc in anchor_desc.descriptors:
        if (desc.tag.identifier == "partition_descriptor"):
            print(f"UDF partition at sector {desc.desc.partition_start}")
            if (partition_start is not None):
                raise Exception("More than one partition descriptor")
            partition_start = desc.desc.partition_start
        if (desc.tag.identifier == "logical_volume_descriptor"):
            print(f"Fileset at sector {desc.desc.content.sector}")
            if (fileset_sector is not None):
                raise Exception("More than one logical volume descriptor")
            fileset_sector = desc.desc.content.sector
    if (partition_start is None):
        raise Exception("No partition descriptor")
    if (fileset_sector is None):
        raise Exception("No logical volume descriptor")
    return ParseUdfPartition(fd, partition_start, fileset_sector)

def ParseIso(fd, parse_iso=True, parse_udf=True):
    files = {}
    vds = IsoVolumeDescriptors.parse_stream(fd)
    for vd in vds:
        if parse_iso and vd.type == 1 and vd.identifier == "CD001":
            print("File has an ISO9660 descriptor")
        if parse_udf and vd.type == 0 and vd.identifier in ["NSR02", "NSR03"]:
            print(f"File has an {vd.identifier} UDF descriptor")
            files["udf"] = ParseUdf(fd, vd.payload)
            # ParseUdfPartition(fd, vd.payload.)
    return files
