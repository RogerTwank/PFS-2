

import os
import numpy as np
import matplotlib.pyplot as plt
import xarray
import subprocess
import pandas as pd
import time
import astropy.io
import random


# this code borrows heavily from the work of Daniel Estevez
# https://destevez.net/2019/11/dslwp-b-crash-site-found/
# Daniel has a much better grasp of python than I do
# I am a C-programmer learning python, so my code is "unpythonic"
# https://stackoverflow.com/questions/19186261/pythonic-vs-unpythonic


# Digital elevation model (DEM) files available at http://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/
    # copy Daniel Estevez code that opens full file
    # modify to work on the global version of the file
def open_dem():
    n_lat, n_lon = 15360, 46080     # points every 0.0078 degrees in lat/long
    lat_min, lat_max = -60.0, 60.0
    lon_min, lon_max = 0.0, 360.0    
    dem_data = np.flipud(np.memmap('sldem2015_128_60s_60n_000_360_float.img', dtype='float32').reshape(n_lat, n_lon))
    dem_full = xarray.DataArray(dem_data,
                            coords = [np.linspace(lat_min, lat_max, n_lat, endpoint = False),
                                     np.linspace(lon_min, lon_max, n_lon, endpoint = False)],
                            dims = ['lat', 'lon'])
 
    # crop down to the rectangle of interest which is
    #   12 S to 12 N
    #   don't crop longitude

    # this should cover all points in all ground tracks
    lon_crop_min = 0.0
    lon_crop_max = 360.0
    lat_crop_min = -12.0
    lat_crop_max = 12.0

    dem_extent = [lon_crop_min, lon_crop_max, lat_crop_min, lat_crop_max]
    dem = dem_full.sel(lon = slice(lon_crop_min,lon_crop_max), lat = slice(lat_crop_min,lat_crop_max))
    return dem, dem_extent


def addAltToGroundTrack( infilename, outfilename, dem):
    """
    Go through an input ground track csv file, with rows of latitude, longitude and altitude data
    Look up the lunar terrain altitude near that location
    Append the terrain altitude and the altitude above terrain to each line
    and write out to a new file.
    :param infilename: name of the input file
    :param outfilename: name of the output file
    :param dem: a 2D DataArray object with lunar altitudes in a lat/long grid
    :return: no return
    """

    outfile = open(outfilename, 'w')
    infile = open(infilename)

    line = infile.readline().strip() #copy over the header with extra column
    outfile.write( line + ", terrain alt, AGL alt\n")
    line = infile.readline().strip()
    while (line != ""):
        MJD, UTC, lon, lat, alt, AZI, HFPA = line.split(',')
        trueAlt = float(alt)
            # ignore parts of each orbit that can't hit terrain
        if trueAlt > 10.0:
            line = infile.readline().strip()
            continue

        demLat = float(lat)
        demLon = float(lon)

        if demLon < 0:
            # convert to 0-360 longitude coordinates used in the DEM file
            demLon = demLon + 360.0       

            # look up the altitude at the DEM grid point nearest this location
        terrainAlt = dem.sel(lat = demLat, lon = demLon, method='nearest')


        # DEM OFFSET is 1737.4 km
        # GMAT Altitude is relative to 1738.0 km
        offsetAlt = terrainAlt.data - 0.6   # shift to the altitude coordinates of GMAT

        trueAlt = float(alt) - offsetAlt  # trueAlt is the altitude above (or below) "ground" in meters
        outfile.write( line + ","+ str(offsetAlt) +","+ str(trueAlt)+ "\n")
        line = infile.readline().strip()


    outfile.write(" \r")


def checkBetweenPoints(infilename, outfilename, dem):
    """
    Go through an input ground track csv file that includes absolute and relative altitude info
    If the AGL altitude is 2km or less, interpolate to the next point
    checking for any possible terrain impact
    Once impact is found write details to output file...
        ...two lines...pre and post impact points
    :param infilename: name of the input file
    :param outfilename: name of the output file
    :param dem: a 2D DataArray object with lunar altitudes in a lat/long grid
    :return: no return
    """

    outfile = open(outfilename, 'w')
    infile = open(infilename)

    # write it in a very unpythonic way
    # read in the first two lines after the header
    # loop until done
        # check the second line for altitude
        # if below 2 km
            # make interpolated arrays of lat/long/alt from first to second lines 
            # for each lat/long/alt in these arrays
                # check for terrain impact
                # if yes, print it out to the console\
                # print the two lines to outfile
                # and done with this infile
        # if not below 2 km
            # second line becomes first line
            # read new second line
            # check for done
        



    done = 0

    firstLine = infile.readline().strip() #copy over the header with extra column
    outfile.write( firstLine + "\n") # add header row

    nextLine = infile.readline().strip()

    while (done != 1 and nextLine != ""):
        prevLine = nextLine
        nextLine = infile.readline().strip()
        MJD2, UTC2, lon2, lat2, alt2, AZI2, HFPA2, terrainAlt2, trueAlt2 = nextLine.split(',')
        trueAltNum = float(trueAlt2)

            # Assumes no hidden peaks greater than this 2 km threshold lurking between points in the input file
        if trueAltNum > 3.0:
            continue
        else:
            MJD1, UTC1, lon1, lat1, alt1, AZI1, HFPA1, terrainAlt1, trueAlt1 = prevLine.split(',')
            numPoints = 100
            latPoints = np.linspace(float(lat1),float(lat2),numPoints).tolist()
            longPoints = np.linspace(float(lon1),float(lon2),numPoints).tolist()
            altPoints = np.linspace(float(alt1),float(alt2),numPoints).tolist()
            MJDPoints = np.linspace(float(MJD1),float(MJD2),numPoints).tolist()
            for i in range(0,numPoints):
                    # look up the altitude at the DEM grid point nearest this location
                terrainAlt = dem.sel(lat = latPoints[i], lon = longPoints[i], method='nearest')

                # DEM OFFSET is 1737.4 km
                # GMAT Altitude is relative to 1738.0 km
                offsetAlt = terrainAlt.data - 0.6   # shift to the altitude coordinates of GMAT
                trueAlt = altPoints[i] - offsetAlt  # trueAlt is the altitude above (or below) "ground" in meters
                #print('Impact Point: {}, Time = {:.9f}, Longitude = {:.4f}, Latitude = {:.4f}, Altitude = {:.4f}'.format(
                #                                        infilename,
                #                                        MJDPoints[i],
                #                                        longPoints[i],
                #                                        latPoints[i],
                #                                        trueAlt))
                if trueAlt < 0:     # impact

                    print('Impact Point: {}, Time = {:.9f}, Longitude = {:.4f}, Latitude = {:.4f}, Altitude = {:.4f}'.format(
                                                            infilename,
                                                            MJDPoints[i],
                                                            longPoints[i],
                                                            latPoints[i],
                                                            trueAlt))

                    done = 1
                    outfile.write( prevLine+'\n') 
                    outfile.write( nextLine+'\n')
                    break


   # I run this twice, uncommenting the different tools and adjusting the paths on each run
def main():

    # set up the DEM array
    dem, dem_extent = open_dem()

        # point to the directory with the input data files
#    inPath = 'C:/Users/roger/Desktop/AGL/'
    inPath = 'C:/Users/roger/Desktop/test/'
    #inPath = 'C:/Users/roger/Desktop/Apollo 10/A16/A16MonteCarlo/A16MonteImpact/AGL'
    os.chdir(inPath)

    timestring = time.strftime("%H%M%S")
    outPath = inPath + '/outfiles'+timestring
    os.mkdir(outPath)

        # first get a list of all the csv files in the directory
    inFileList = os.listdir(inPath)
    for fileName in inFileList:
        if fileName.endswith(".csv"):
            outFileName = outPath + '/'+ fileName

                # first time through the file, uncomment this line to add the true altitude
#            addAltToGroundTrack( fileName, outFileName, dem)    
            
                # second time through the file, uncomment this line to check between every pair of low points for a possible impact   
            checkBetweenPoints(fileName, outFileName, dem)



main()
