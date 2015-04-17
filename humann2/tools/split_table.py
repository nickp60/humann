#!/usr/bin/env python

"""
Split a gene/pathway table into a table per sample

This module will create gene tables used as input by HUMAnN2. 

Dependencies: Biom (only required if running with .biom files)

To Run: 
$ ./split_table.py -i <gene_table.{tsv,biom}> -o <output_dir>

"""

import argparse
import sys
import tempfile
import os
import re
import shutil

import util

GENE_TABLE_DELIMITER="\t"
GENE_TABLE_COMMENT_LINE="^#"
BIOM_FILE_EXTENSION=".biom"
TSV_FILE_EXTENSION=".tsv"
TAXONOMY_DELIMITER="; "
PICRUST_METAGENOME_HEADER="Kingdom\tPhylum\tClass\tOrder\tFamily\tGenus\tSpecies"
PICRUST_METAGENOME_SAMPLE_COLUMN=1
PICRUST_METAGENOME_GENE_COLUMN=0
PICRUST_METAGENOME_ABUNDANCE_COLUMN=2
PICURST_METAGENOME_GENUS_COLUMN=13
PICURST_METAGENOME_SPECIES_COLUMN=14
        
def split_gene_table(gene_table,output_dir, verbose=None, taxonomy_index=None):
    """
    Split the gene table into a table per sample
    """
    
    # try to open the file
    try:
        file_handle=open(gene_table,"r")
        line=file_handle.readline()
    except EnvironmentError:
        sys.exit("Unable to read file: " + gene_table)
            
    # find the headers
    header_flag=False
    header=line
    while re.match(GENE_TABLE_COMMENT_LINE, line):
        header_flag=True
        header = line
        line = file_handle.readline()
        
    # if no headers are present, then use the first line as the header
    if not header_flag:
        line = file_handle.readline()
        
    # check for picrust metagenome file format
    if re.search(PICRUST_METAGENOME_HEADER,header):
        new_file_names=split_table_sample_rows(file_handle, line, output_dir, verbose)
    else:
        new_file_names=split_table_sample_columns(file_handle, header, line, output_dir, taxonomy_index, verbose)
        
    return new_file_names


def split_table_sample_rows(file_handle, line, output_dir, verbose):
    """
    Split a table where the samples are indicated in each row
    """
    
    # create files for each sample
    new_file_names=[]
    
    gene_table_data_by_sample_bug={}
    while line:
        # read in each line of data
        data=line.rstrip().split(GENE_TABLE_DELIMITER)        
        gene=data[PICRUST_METAGENOME_GENE_COLUMN]
        abundance=data[PICRUST_METAGENOME_ABUNDANCE_COLUMN]
        
        try:
            abundance=float(abundance)
        except ValueError:
            abundance=0
        
        sample=data[PICRUST_METAGENOME_SAMPLE_COLUMN]
        try:
            bug="g__"+data[PICURST_METAGENOME_GENUS_COLUMN]+".s__"+data[PICURST_METAGENOME_SPECIES_COLUMN]
        except IndexError:
            bug=""
        
        # sum the abundance data by sample and bug
        if not sample in gene_table_data_by_sample_bug:
            gene_table_data_by_sample_bug[sample]={}
            
        if not gene in gene_table_data_by_sample_bug[sample]:
            gene_table_data_by_sample_bug[sample][gene]={}
            
        gene_table_data_by_sample_bug[sample][gene][bug]=gene_table_data_by_sample_bug[sample][gene].get(bug,0)+abundance
        line = file_handle.readline()
        
    file_handle.close()
        
    # write the genes to the files
    for sample in gene_table_data_by_sample_bug:
        simple_sample_name=re.sub("[^a-zA-Z0-9_|-|.]|@|\\?|\\]|\\[|\\^","_",sample)
        try:
            new_file_name=os.path.join(output_dir,simple_sample_name+TSV_FILE_EXTENSION)
            if verbose:
                print "Creating file: " + new_file_name
            new_file_names.append(new_file_name)
            new_file_handle=open(new_file_name,"w")
            
            # write the header
            new_file_handle.write(GENE_TABLE_DELIMITER.join(["#OTU ID",sample])+"\n")
            
            # write all of the abundance data
            for gene in gene_table_data_by_sample_bug[sample]:
                total=0
                new_lines=[]
                for bug in gene_table_data_by_sample_bug[sample][gene]:
                    total+=gene_table_data_by_sample_bug[sample][gene][bug]
                    if bug:
                        new_lines.append(GENE_TABLE_DELIMITER.join([gene+"|"+bug,
                            str(gene_table_data_by_sample_bug[sample][gene][bug])])+"\n")
                    
                new_file_handle.write(GENE_TABLE_DELIMITER.join([gene,str(total)])+"\n")
                if new_lines:
                    new_file_handle.write("".join(new_lines))
                    
            new_file_handle.close()
            
        except EnvironmentError:
            sys.exit("Unable to create split gene table files") 
    
    return new_file_names   
    
    

def split_table_sample_columns(file_handle, header, line, output_dir, taxonomy_index, verbose):
    """
    Split a table where the abundances of genes are organized by sample in columns
    """
    
    samples=header.rstrip().split(GENE_TABLE_DELIMITER)    
    
    # create files for each sample
    new_file_handles=[]
    new_file_names=[]
    sample_names=samples[1:]
    
    # if taxonomy is set the last column is not a sample but taxonomy
    # taxonomy_index can be set to zero
    if taxonomy_index != None:
        header_taxonomy=samples.pop()
    
    for sample in samples[1:]:
        simple_sample_name=re.sub("[^a-zA-Z0-9_|-|.]|@|\\?|\\]|\\[|\\^","_",sample)
        try:
            new_file_name=os.path.join(output_dir,simple_sample_name+TSV_FILE_EXTENSION)
            new_file_names.append(new_file_name)
            new_file_handle=open(new_file_name,"w")
            new_file_handles.append(new_file_handle)
            
            # write the header
            new_file_handle.write(GENE_TABLE_DELIMITER.join([samples[0],sample])+"\n")
        except EnvironmentError:
            sys.exit("Unable to create split gene table files")
    
    gene_table_data_by_column={}
    while line:
        # write the data to each of the new files
        data=line.rstrip().split(GENE_TABLE_DELIMITER)        
        gene=data.pop(0)
        # process the taxonomy
        # taxonomy_index can be set to zero
        if taxonomy_index != None:
            # taxonomy data is the last column
            taxonomy_data=data.pop().split(TAXONOMY_DELIMITER)
            try:
                gene=taxonomy_data[taxonomy_index]
            except IndexError:
                sys.exit("The taxonomy index provided is not valid: " + str(taxonomy_index))
                
        for i, data_point in enumerate(data):
            try:
                float_data_point=float(data_point)
            except ValueError:
                float_data_point=0
            
            if i in gene_table_data_by_column:
                # add the data point to the other data for the gene
                gene_table_data_by_column[i][gene]=gene_table_data_by_column[i].get(gene,0)+float_data_point
            else:
                gene_table_data_by_column[i]={gene : float_data_point}
        line = file_handle.readline()
        
    file_handle.close()
        
    # write the genes to the files
    for i,new_file_handle in enumerate(new_file_handles):
        if verbose:
            print "Creating file: " + new_file_names[i]
        for gene in gene_table_data_by_column.get(i,{}):
            data_point=str(gene_table_data_by_column[i].get(gene,0))
            new_file_handle.write(GENE_TABLE_DELIMITER.join([gene,data_point])+"\n")
        new_file_handle.close()   
    
    return new_file_names

def parse_arguments(args):
    """ 
    Parse the arguments from the user
    """
    
    parser = argparse.ArgumentParser(
        description= "Split gene table to input to HUMAnN2\n",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-v","--verbose", 
        help="additional output is printed\n", 
        action="store_true",
        default=False)
    parser.add_argument(
        "-i","--input",
        help="the gene table to read\n",
        required=True)
    parser.add_argument(
        "-o","--output",
        help="the directory for output files\n",
        required=True)
    parser.add_argument(
        "--taxonomy_index",
        help="the index of the gene in the taxonomy data\n",
        type=int)

    return parser.parse_args()


def main():
    # Parse arguments from command line
    args=parse_arguments(sys.argv)
    
    # Check for the biom software if running with a biom input file
    biom_flag=False
    if args.input.endswith(BIOM_FILE_EXTENSION):
        biom_flag=True
        if not util.find_exe_in_path("biom"):
            sys.exit("Could not find the location of the biom software."+
                " This software is required since the input file is a biom file.")
    
    args.input=os.path.abspath(args.input)
    
    output_dir=os.path.abspath(args.output)
    
    if not os.path.isfile(args.input):
        sys.exit("The gene table provided is not a file. Please enter a new file.")
    
    if not os.access(args.input, os.R_OK):
        sys.exit("The gene table provided is not readable. Please update the permissions.")
        
    if not os.path.isdir(output_dir):
        if args.verbose:
            print("Creating output directory: " + output_dir)
        try:
            os.mkdir(output_dir)
        except EnvironmentError:
            sys.exit("Unable to create output directory.")
            
    if not os.access(output_dir, os.W_OK):
        sys.exit("The output directory provided is not writeable. Please update the permissions.")
    
    # Create a temp folder for the biom conversions
    if biom_flag:
        temp_dir=tempfile.mkdtemp( 
            prefix='humann2_split_gene_tables_', dir=output_dir)
        if args.verbose:
            print("Temp folder created: " + temp_dir)
        
    if biom_flag:
        # create a new temp file
        file_out, new_file=tempfile.mkstemp(dir=temp_dir)
        os.close(file_out)
        
        # convert biom file to tsv
        util.biom_to_tsv(args.input,new_file,taxonomy=args.taxonomy_index)
        
    # split the gene table
    if args.verbose:
        print("Spliting gene table")
        
    if biom_flag:
        new_file_names=split_gene_table(new_file,temp_dir,taxonomy_index=args.taxonomy_index)
    else:
        new_file_names=split_gene_table(args.input,output_dir,verbose=args.verbose)
        
    if args.verbose:
        print("Gene table has been split into " + str(len(new_file_names)) + " total files")
        
    # convert all gene tables to biom
    for file in new_file_names:
        if biom_flag:
            new_file=os.path.join(output_dir,os.path.basename(file))
            new_file=re.sub(TSV_FILE_EXTENSION+"$",BIOM_FILE_EXTENSION,new_file)
            util.tsv_to_biom(file,new_file)
            print("Creating file: " + new_file)
            
    # deleting temp folder with all files
    if biom_flag:
        if args.verbose:
            print("Deleting temp files in temp folder: " + temp_dir)
        shutil.rmtree(temp_dir)
    
    print("All gene tables created: " + output_dir)

if __name__ == "__main__":
    main()
