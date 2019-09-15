/* fiximage version 0.1
 *
 * If you use this source code in your own project,
 * you have to retain this notice and post the source
 * of your project as well. For further information,
 * refer to the GPL licence.
 * 
 * fiximage corrects images ripped using cobra ode.
 * It needs information about the invalid cbc offset
 * used by the internal ps3 crypto engine to reverse
 * the cbc and re-apply it with the correct offset.
 */

#include <stdio.h>
#include <stdlib.h>
#include <byteswap.h>

#define SECTOR_SIZE 2048

typedef struct {
  int start;
  int end;
} disc_region_t;

int main(int argc, char** argv) {
  if( argc != 3 ) {
    printf("Usage: %s <COBRA.NFO> <DISC.ISO>\n", *argv);
    printf("Extracts LBA offset from COBRA.NFO and tries to correct DISC.ISO\n");
    printf("COBRA.NFO has to be copied aside the image. Filenames may differ.\n");
    return 1;
  }

  argv++;
  FILE* file_nfo = fopen(*argv,"r");
  if( !file_nfo ) {
    printf("failed to open nfo file %s\n", *argv);
    return 1;
  }

  //read lba offset from file_nfo
  fseek( file_nfo, 2, SEEK_SET );
  int lba_offset = 0;
  int units_read = fread(&lba_offset, sizeof(int), 1, file_nfo);
  if( units_read < 1 )  {
    printf("Failed to read from nfo file\n");
    return 1;
  }
  fclose(file_nfo);
  printf("got lba sector offset %#010x from nfo\n", lba_offset);

  argv++;
  FILE* file_image = fopen(*argv,"r+");
  if( !file_image ) {
    printf("failed to open image file %s\n", *argv);
    return 1;
  }

  printf("sector size is %d bytes per sector\n", SECTOR_SIZE);

  //get number of plain regions
  int num_plain_regions = 0;
  units_read = fread(&num_plain_regions, sizeof(int), 1, file_image);
  if( units_read < 1 )  {
    printf("Failed to read from image file\n");
    return 1;
  }
  num_plain_regions = bswap_32(num_plain_regions);
  printf("this ISO has %d plain regions:\n", num_plain_regions);

  //get plain regions dimensions
  fseek( file_image, 4, SEEK_CUR ); //skip 4 garbage zero bytes
  disc_region_t plain_regions[num_plain_regions];
  for( unsigned int region = 0; region < num_plain_regions; region++ ) {
    units_read = fread(&plain_regions[region].start, sizeof(int), 2, file_image);
    plain_regions[region].start = bswap_32(plain_regions[region].start);
    plain_regions[region].end = bswap_32(plain_regions[region].end);
    if( units_read < 2 ) {
      printf("failed to plain region #%d info\n", region);
      return 1;
    }
    if( plain_regions[region].start >= plain_regions[region].end )  {
      printf("plain region %d has start after or equal end, corrupt image?\n", region);
      return 1;
    }
    printf("plain region %d sectors: start %#010x end %#010x length %#010x\n", region, plain_regions[region].start, plain_regions[region].end, plain_regions[region].end-plain_regions[region].start+1);
  }

  //search encrypted regions between plain ones
  int num_encrypted_regions = 0;
  for( unsigned int region = 0; region < num_plain_regions-1; region++ ) {
    if( plain_regions[region].end+1 == plain_regions[region+1].start )
      printf("plain regions %d and %d fit seamlessly, no encrypted region in between\n", region, region+1);
    else
      num_encrypted_regions++;
  }
  printf("found %d encrypted regions between plain ones:\n", num_encrypted_regions);

  //collect start/end of encrypted regions, cloud have been done without
  disc_region_t encrypted_regions[num_encrypted_regions];
  int found_encrypted_regions = 0;
  for( unsigned int region = 0; region < num_plain_regions-1; region++ )
    if( plain_regions[region].end+1 != plain_regions[region+1].start ) {
      encrypted_regions[found_encrypted_regions].start = plain_regions[region].end+1;
      encrypted_regions[found_encrypted_regions].end = plain_regions[region+1].start-1;
      printf("encrypted region %d sectors: start %#010x end %#010x length %#010x\n", found_encrypted_regions, encrypted_regions[found_encrypted_regions].start, encrypted_regions[found_encrypted_regions].end, encrypted_regions[found_encrypted_regions].end-encrypted_regions[found_encrypted_regions].start+1);
      found_encrypted_regions++;
    }
  if( num_encrypted_regions != found_encrypted_regions ) {
    printf("something is wrong, did not find all encrypted regions\n");
    return 1;
  }

  //correct encrypted regions
  for( unsigned int region = 0; region < num_encrypted_regions; region++ ) {
    printf("correcting encrypted region %d\n", region);

    //loop through all sectors in that region to correct each sectors' first 16 bytes
    for( unsigned int region_sector = encrypted_regions[region].start; region_sector <= encrypted_regions[region].end; region_sector++ ) {
      //display some progress
      if( (region_sector-encrypted_regions[region].start) % 200000 == 0 )
        printf("region %d: %d sectors done\n", region, region_sector-encrypted_regions[region].start);

      //seek to sector
      if( fseek(file_image, (long int)region_sector * SECTOR_SIZE, SEEK_SET) ) {
        printf("failed to seek to sector %#010x\n", region_sector);
        continue;
      }

      //read first 16 bytes from sector
      int buffer[4];
      units_read = fread(buffer, sizeof(int), 4, file_image);
      if( units_read < 4 ) {
        printf("failed to read 4 bytes at sector %#010x\n", region_sector);
        continue;
      }

      //printf("original sector data:  %#010x %#010x %#010x %#010x\n", buffer[0], buffer[1], buffer[2], buffer[3]);
      //big-to-little-endian, decode cbc, re-encode corrent cbc, little-to-big-endian
      for( int i = 3; i < 4; i++ ) { //COBRA manual tells us to correct all 16 bytes, my experiments showed that we just need to correct byte 12-15
        buffer[i] = bswap_32(buffer[i]);
        buffer[i] ^= lba_offset + region_sector;
        buffer[i] ^= region_sector;
        buffer[i] = bswap_32(buffer[i]);
      }
      //printf("corrected sector data: %#010x %#010x %#010x %#010x\n", buffer[0], buffer[1], buffer[2], buffer[3]);

      //write corrected bytes
      fseek(file_image, (long int)region_sector * SECTOR_SIZE, SEEK_SET);
      units_read = fwrite(buffer, sizeof(int), 4, file_image);
      if( units_read < 4 )
        printf("failed to write 4 bytes at sector %#010x\n", region_sector);
    }
    printf("region %d: %d sectors done\n", region, encrypted_regions[region].end+1-encrypted_regions[region].start);
  }

  fclose(file_image);
  return 0;
}
