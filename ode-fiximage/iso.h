#include <stdint.h>

typedef struct {
  int8_t type_code;
  char std_identifier[5];
  int8_t std_version;
  int8_t unused0;
  char sys_identifier[32];
  char vol_identifier[32];
  char unused1[8];
  int32_t vol_space_size;
  int32_t vol_space_size_be;
  char unused2[32];
  int16_t vol_set_size;
  int16_t vol_set_size_be;
  int16_t vol_sequence_number;
  int16_t vol_sequence_number_be;
  int16_t logical_block_size;
  int16_t logical_block_size_be;
  int32_t path_table_size;
  int32_t path_table_size_be;
  int32_t lpath_table_sector;
  int32_t opt_lpath_table_sector;
  int32_t mpath_table_sector_be;
  int32_t opt_mpath_table_sector_be;
  char root_directory[34];
  char vol_set_identifier[128];
  char publisher_identifier[128];
  char data_preparer_identifier[128];
  char application_identifier[128];
  char copyright_file_identifier[38];
  char abstract_file_identifier[36];
  char bibliographic_file_identifier[37];
  char vol_creation_date[17];
  char vol_modification_date[17];
  char vol_expiration_date[17];
  char vol_effective_date[17];
  int8_t file_structure_version;
  int8_t unused3;
  char unused[512];
  char reserved[653];
} __attribute__ ((__packed__)) primary_volume_descriptor_t;

typedef struct directory_record_t directory_record_t;
struct directory_record_t {
  int8_t length;
  int8_t extended_attr_length;
  int32_t data_sector;
  int32_t data_sector_be;
  int32_t data_length;
  int32_t data_length_be;
  char date[7];
  int8_t flags;
  int8_t interleave_unit_size;
  int8_t interleave_gap;
  int16_t vol_sequence_number;
  int16_t vol_sequence_number_be;
  int8_t name_length;
  char name[223]; //max length of whole directory_record is 256 bytes
  directory_record_t* next;
  directory_record_t* previous;
} __attribute__ ((__packed__));

typedef struct path_table_entry_t path_table_entry_t;
struct path_table_entry_t {
  int8_t length;
  int8_t extended_attr_length;
  int32_t data_sector;
  int16_t parent_dir_number;
  char* dirname;
  struct path_table_entry_t* parent;
  struct path_table_entry_t* next;
  struct path_table_entry_t* previous;
  struct directory_record_t* dir_record;
}  __attribute__ ((__packed__));
