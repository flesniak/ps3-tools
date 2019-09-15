#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "iso.h"

#define SECTOR_SIZE 2048

static primary_volume_descriptor_t pvd;
static path_table_entry_t* path_table;

char* createPathString(path_table_entry_t* pte) {
  static char path[256];
  strcpy(path, "/");
  char temp[256];
  while( pte != 0 && pte != pte->parent ) {
    temp[0] = 0;
    strcat(temp, "/");
    strcat(temp, pte->dirname);
    strcat(temp, path);
    strcpy(path, temp);
    pte = pte->parent;
  }
  return path;
}

path_table_entry_t* getParent(int index) {
  path_table_entry_t* pte = path_table;
  for( int i=1; i<index; i++ ) {
    if( pte->next )
      pte = pte->next;
    else
      return 0; //not enough path table entries
  }
  return pte;
}

//creates a dynamic double linked list of directory_records that begin at sector
directory_record_t* assemble_directory_records(FILE* isofile, int32_t sector) {
  printf("assembling directories at sector %#010x (%d)\n", sector, sector);
  if( fseek(isofile, sector * SECTOR_SIZE, SEEK_SET) ) {
    printf("failed to seek to directory record at sector %#010x (%d)\n", sector, sector);
    return 0;
  }

  int32_t bytes_processed = 0;
  directory_record_t* first_directory_record = malloc(sizeof(directory_record_t));
  first_directory_record->previous = first_directory_record->next = 0;
  directory_record_t* current_directory_record = first_directory_record;
  while( 1 ) {
    int units_read = fread(current_directory_record, 33, 1, isofile);
    if( units_read < 1 ) {
      printf("failed to directory record at byte %d\n", sector*SECTOR_SIZE + bytes_processed);
      return first_directory_record;
    }
    if( current_directory_record->length <= 33 ) { //we found the end
      if( current_directory_record->length > 0 )
        printf("invalid directory record length %d found at byte %d\n", current_directory_record->length, sector*SECTOR_SIZE + bytes_processed);
      break;
    }
    bytes_processed += 33;
    units_read = fread(current_directory_record->name, current_directory_record->length-33, 1, isofile);
    if( units_read < 1 ) {
      printf("failed to directory record name field at byte %d\n", sector*SECTOR_SIZE + bytes_processed);
      return first_directory_record;
    }
    if( current_directory_record->name_length == 0 )
      printf("bad name length 0 in directory record at byte %d, ignoring\n", sector*SECTOR_SIZE + bytes_processed);
    else {
      if( current_directory_record->name_length == 1 )
        switch( current_directory_record->name[0] ) {
          case 0 :
            strcpy(current_directory_record->name, ".");
            break;
          case 1 :
            current_directory_record->name[0] = 0;
            strcpy(current_directory_record->name, "..");
            break;
          default :
            break;
        }
      else //normally bogus bytes are set to zero, but lets be sure to have null-terminated names
        current_directory_record->name[current_directory_record->name_length] = 0;
    }
    bytes_processed += current_directory_record->length-33;

    printf("file \"%s\" data sector %#010x length %#010x\n", current_directory_record->name, current_directory_record->data_sector, current_directory_record->data_length);

    current_directory_record->next = malloc(sizeof(directory_record_t));
    current_directory_record->next->previous = current_directory_record;
    current_directory_record = current_directory_record->next;
  }
  if( current_directory_record != first_directory_record ) {
    current_directory_record->previous->next = 0; //end of list
    free(current_directory_record); //delete needlessly allocated record
    return first_directory_record;
  } else {
    free(first_directory_record);
    printf("no directory records found at sector %#010x (%d)!\n", sector, sector);
    return 0;
  }
}

//creates a dynamic double linked list of directory_records that reside inside the directory pointed to by parent_pte
directory_record_t* assemble_directory_records_pte(FILE* isofile, path_table_entry_t* parent_pte) {
  printf("going to assemble contents of directory %s\n", createPathString(parent_pte));
  return assemble_directory_records(isofile, parent_pte->data_sector);
}

int parse_path_table(FILE* isofile) {
  if( fseek(isofile, pvd.lpath_table_sector * SECTOR_SIZE, SEEK_SET) ) {
    printf("failed to seek to path table sector %#010x (%d)\n", pvd.lpath_table_sector, pvd.lpath_table_sector);
    return 0;
  }
  int bytes_processed = 0;
  path_table_entry_t* current_path_table_entry = malloc(sizeof(path_table_entry_t));
  path_table = current_path_table_entry;
  path_table->previous = 0;

  int entries = 0;
  while( bytes_processed < pvd.path_table_size ) {
    //verbose output
    printf("processing path table at byte %#010x (%d)\n", (unsigned int)ftell(isofile), (unsigned int)ftell(isofile));

    //read path table entry header (8 bytes)
    current_path_table_entry->next = current_path_table_entry->parent = 0;
    current_path_table_entry->dir_record = 0;
    int units_read = fread(current_path_table_entry, 8, 1, isofile);
    if( units_read < 1 ) {
      printf("failed to read path table entry\n");
      return entries;
    }
    if( current_path_table_entry->length == 0 ) {
      printf("last path table entry found before end, %d bytes processed, path table size %d\n", bytes_processed, pvd.path_table_size);
      break;
    }

    //allocate space for dirname (plus \0) and read it
    current_path_table_entry->dirname = malloc(current_path_table_entry->length+1);
    units_read = fread(current_path_table_entry->dirname, current_path_table_entry->length, 1, isofile);
    if( units_read < 1 ) {
      printf("failed to read directory name\n");
      return entries;
    }

    //skip 1 padding byte if length is odd
    if( current_path_table_entry->length % 2 ) {
      fseek(isofile, 1, SEEK_CUR);
      bytes_processed++;
    }

    //put \0 as last character, calculate bytes and increment entry count
    current_path_table_entry->dirname[current_path_table_entry->length] = 0;
    current_path_table_entry->parent = getParent(current_path_table_entry->parent_dir_number);
    if( current_path_table_entry->parent == 0 )
      printf("failed to get parent dir entry pointer\n");
    bytes_processed += 8 + current_path_table_entry->length;
    entries++;

    printf("entry data at %#010x parent %d \"%s\"\n", current_path_table_entry->data_sector, current_path_table_entry->parent_dir_number, current_path_table_entry->dirname);
//     if( current_path_table_entry->parent )
//       printf(" parent %s\n", current_path_table_entry->parent->dirname);
//     else
//       printf("\n");
    //printf("own ptr %#010x parent %#010x\n", current_path_table_entry, current_path_table_entry->parent);
    printf("%s\n", createPathString(current_path_table_entry));
    printf("\n");

    current_path_table_entry->next = malloc(sizeof(path_table_entry_t));
    current_path_table_entry->next->previous = current_path_table_entry;
    current_path_table_entry = current_path_table_entry->next;
  }
  current_path_table_entry->previous->next = 0;
  free(current_path_table_entry);
  return entries;
}

int main(int argc, char** argv) {
  if( argc != 2 ) {
    fprintf(stderr, "usage: %s <file.iso>\n", *argv);
    exit(1);
  }

  argv++;
  FILE* isofile = fopen(*argv,"r");
  if( !isofile ) {
    fprintf(stderr, "failed to open iso file %s\n", *argv);
    exit(1);
  }

  //seek to first volume descriptor
  if( fseek(isofile, 0x10 * SECTOR_SIZE, SEEK_SET) ) {
    printf("failed to seek to sector 0x10\n");
    exit(1);
  }
  int units_read = fread( &pvd, 2048, 1, isofile);
  if( units_read < 1 ) {
    printf("failed to read primary volume descriptor\n");
    exit(1);
  }
  if( pvd.type_code != 1 ) {
    printf("first volume descriptor is no primary one! searching it is not implemented yet!\n");
    exit(1);
  }

  printf("primary volume descriptor:\n");
  printf("vol_space_size        %#010x (%d)\n", pvd.vol_space_size, pvd.vol_space_size);
  printf("path_table_size       %#010x (%d)\n", pvd.path_table_size, pvd.path_table_size);
  printf("lpath_table_sector    %#010x (%d)\n", pvd.lpath_table_sector, pvd.lpath_table_sector);
  printf("mpath_table_sector_be %#010x (%d)\n", pvd.mpath_table_sector_be, pvd.mpath_table_sector_be);
  printf("\n");

  directory_record_t root_dir;
  memcpy( &root_dir, pvd.root_directory, 34);
  printf("root directory:\n");
  printf("data_sector     %#010x (%d)\n", root_dir.data_sector, root_dir.data_sector);
  printf("data_length     %#010x (%d)\n", root_dir.data_length,  root_dir.data_length);
  printf("flags           %#010x (%d)\n", root_dir.flags, root_dir.flags);
  printf("filename_length %#010x (%d)\n", root_dir.name_length, root_dir.name_length);
  printf("\n");

  parse_path_table(isofile);

  for( path_table_entry_t* pte = path_table; pte != 0; pte = pte->next )
    pte->dir_record = assemble_directory_records_pte(isofile, pte);

  return 0;
}
