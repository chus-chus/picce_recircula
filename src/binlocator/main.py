#!/usr/bin/python3

""" MIT License, 2021 @
     Cristina Aguilera (cristina.aguilera.gonzalez@estudiantat.upc.edu)
     Jesus Antonanzas (jesus.maria.antonanzas@estudiantat.upc.edu)
     Irene Josa (irene.josa@upc.edu)
     Paz Ripoll (paz.ripoll@estudiantat.upc.edu)
     Estel Rueda (estel.rueda@upc.edu) """

import warnings
import gmplot
import requests

import pandas as pd
import numpy as np

from sodapy import Socrata
from datetime import datetime, timedelta
from tqdm import tqdm
from geopy import distance as coord_distance

from clean_population import clean_pop
from arguments import get_arguments
from src.binlocator.keys import INCOMPLETE_POINTS_NAME, DATA_PATH, POINTS_NAME, POPULATION_DATA_NAME, \
    POINTS_PICKED_LIST_NAME, POINTS_PICKED_MAP_NAME, OUTPUT_PATH


def compute_distances(points):
    """ Inserts N columns in the 'points' DF, where N is the number of points. Each column contains the distance to
     a particular points in the DF (in km). """

    distances = points
    # create new distance columns
    for pointID in points.index:
        distances.loc[:, 'dist' + str(pointID)] = None
    for pointID, latitude, longitude in zip(points.index, points['latitude'], points['longitude']):
        for columnID in points.index:
            if pointID == columnID:
                distance = 0
            else:
                firstCoords = (latitude, longitude)
                secondCoords = (points.loc[columnID, 'latitude'], points.loc[columnID, 'longitude'])
                distance = coord_distance.distance(firstCoords, secondCoords).km
            distances.loc[pointID, 'dist' + str(columnID)] = distance
    return distances


def abs_densities(cases, densityCover):
    """ Returns pandas DF containing the infection density for the ABS that account for the top 'densityCover'
    infection density. """
    totalCases = cases['numcasos'].sum()
    cases = cases.groupby(by='abscodi').sum('numcasos')
    cases = cases.rename({'numcasos': 'infectionDensity'}, axis=1)
    cases['infectionDensity'] = cases['infectionDensity'] / totalCases

    # pick top ABSs
    cases = cases.sort_values(by='infectionDensity', ascending=False)
    density = 0
    for i, infectionDensity in enumerate(cases['infectionDensity']):
        density += infectionDensity
        if density >= densityCover:
            cases = cases.iloc[:i+1]
            break
    return cases


def query_cases(client, sanitaryRegion, daysBefore):
    """ Query cases looking at daysBefore days past from the specified sanitary region """

    # Casos covid Regio Sanitaria Barcelona Ciutat:
    # https://analisi.transparenciacatalunya.cat/ca/Salut/Registre-de-casos-de-COVID-19-realitzats-a-Catalun/xuwf-dxjd

    firstDate = (datetime.today() - timedelta(days=daysBefore)).isoformat()

    sanitaryRegion = "'" + str(sanitaryRegion) + "'"
    firstDate = "'" + firstDate + "'"

    queryCases = "regiosanitariacodi == {} AND data >= {}".format(sanitaryRegion, firstDate)
    resultsCases = client.get_all("xuwf-dxjd", where=queryCases)  # iterator
    rows = [pd.DataFrame.from_records(next(resultsCases), index=[0])]

    print('Fetching COVID-19 cases since {}...'.format(firstDate))
    for i, row in tqdm(enumerate(resultsCases, start=1)):
        rows.append(pd.DataFrame.from_records(row, index=[i]))

    casesBCN = pd.concat(rows).astype({'numcasos': int})
    casesBCN['data'] = pd.to_datetime(casesBCN['data'])

    return casesBCN


def download_process_drugstores(client, ABSs, apiKey, sanitaryRegion):
    """ Downloads catalan drug stores, picks the ones from the ABSs of the picked sanitary region
    and searches for their coordinates, saving the info as a CSV for later use.

    https://analisi.transparenciacatalunya.cat/Salut/Cat-leg-de-farm-cies-de-Catalunya/f446-3fny
    """

    resultsDrugStores = client.get_all("f446-3fny")
    rows = [pd.DataFrame.from_records(next(resultsDrugStores), index=[0])]

    print('\n Fetching available bin points...')
    for i, row in tqdm(enumerate(resultsDrugStores, start=1)):
        rows.append(pd.DataFrame.from_records(row, index=[i]))

    drugStoresDf = pd.concat(rows).loc[:, ['codi_abs', 'tipus_via', 'nom_via', 'num_via', 'codi_postal']]
    drugStoresDf = drugStoresDf.rename({'codi_abs': 'abscodi'}, axis=1)

    # Process points only within the selected sanitary region
    drugStoresInAbs = drugStoresDf.loc[:, 'abscodi'].apply(lambda t: t in ABSs)
    drugStoresDf = drugStoresDf.loc[drugStoresInAbs, :]

    # Clean point directions
    drugStoresDf = drugStoresDf.loc[drugStoresDf['num_via'] != 'S/N', :]

    streetTypes = {'CR': 'Carrer', 'GV': 'Gran Via', 'PL': 'Plaça', 'RB': 'Rambla', 'AV': 'Avinguda',
                   'TS': 'Travessera', 'RD': 'Ronda', 'PS': 'Passeig', 'MO': 'Monestir', 'VI': 'Via', 'PG': 'Passatge',
                   'RI': 'Riera', 'TO': 'Torrent', 'BX': 'Baixada', 'CT': 'Carretera'}
    drugStoresDf['tipus_via'] = drugStoresDf['tipus_via'].apply(lambda t: streetTypes[t])

    drugStoresDf['direction'] = (drugStoresDf['tipus_via'] + " " + drugStoresDf['nom_via'] + " " +
                                 drugStoresDf['num_via'] + ", " + drugStoresDf['codi_postal'] + " Barcelona")
    drugStoresDf = drugStoresDf.drop(['tipus_via', 'nom_via', 'num_via', 'codi_postal'], axis=1)

    # get coordinates from google maps queries
    latitudes = []
    longitudes = []
    wrongDirections = []
    anyWrongPetition = False
    print("\n Geocoding points' coordinates...")
    for direction in tqdm(drugStoresDf['direction']):
        direction = direction.replace(' ', '+')
        apiURL = "https://maps.googleapis.com/maps/api/geocode/json?address={}&key={}".format(direction, apiKey)
        addressInfo = requests.get(apiURL).json()
        if addressInfo['status'] != 'OK':
            warnings.warn('Some addresses coordinates could not be found: PETITION ERROR ' + addressInfo['status'])
            wrongDirections.append(direction)
            latitudes.append(None)
            longitudes.append(None)
            anyWrongPetition = True
        else:
            latitudes.append(addressInfo['results'][0]['geometry']['location']['lat'])
            longitudes.append(addressInfo['results'][0]['geometry']['location']['lng'])
    drugStoresDf['latitude'] = latitudes
    drugStoresDf['longitude'] = longitudes
    print('Points saved.')
    drugStoresDf.to_csv(DATA_PATH + POINTS_NAME + str(sanitaryRegion) + '.csv', index=False)
    if anyWrongPetition:
        warnings.warn('Please manually correct the addresses in {}'.format(DATA_PATH + INCOMPLETE_POINTS_NAME + '.txt'))
        with open(DATA_PATH + INCOMPLETE_POINTS_NAME + '.txt', 'w') as file:
            for listitem in wrongDirections:
                file.write('%s\n' % listitem)


def compute_nbins_in_abs(points, absDensities, maxBins, exactBins):
    """ Compute the number of bins to go in each ABS (bins proportional to the partial infection density of the picked
    ABSs). Partial infection density is the proportion of cases among the chosen ABSs. Note that there cannot
    be more bins assigned than the number of points. """

    absDensities['partInfectionDensity'] = absDensities['infectionDensity'] / sum(absDensities['infectionDensity'])
    nBins = []
    for ABScode, partialDensity in zip(absDensities.index, absDensities['partInfectionDensity']):
        numberOfPoints = len(points.loc[points['abscodi'] == ABScode, :].index)
        binsPicked = round(partialDensity * maxBins)
        if binsPicked == 0:
            binsPicked = 1
        elif binsPicked > numberOfPoints:
            binsPicked = numberOfPoints
        nBins.append(binsPicked)
    if exactBins and sum(nBins) > maxBins:
        # the total number of bins used may be greater than the max. to better fit the partial infection densities
        i = len(nBins) - 1
        while i >= 0 and sum(nBins) > maxBins:
            if nBins[i] > 1:
                nBins[i] -= 1
            i -= 1
    if sum(nBins) > maxBins:
        warnings.warn('Maximum number of bins is too low for decent coverage, using {} bins'.format(sum(nBins)))
    return nBins


def pick_points_by_distance(distances, nBins):
    """ Greedily pick 'nBins' points to maximize cover area in a given ABS.
           1) find point furthest from all and pick it
           2) find point furthest from the picked points (maximizes the sum of distances)
           3) repeat '2' until no more points have to be picked """

    pickedPoints = []
    for i in range(nBins):
        availablePoints = distances.index.tolist()
        maxDist = -np.inf
        pickedPoint = None
        # search for furthest point to all of them if no point has been picked, else search for point furthest
        # from the already picked points
        pointsToCompare = availablePoints if pickedPoint is None else pickedPoints
        for pointID in availablePoints:
            distSum = 0
            for colID in pointsToCompare:
                distSum += distances.loc[pointID, 'dist' + str(colID)]
            if distSum > maxDist:
                pickedPoint = pointID
                maxDist = distSum
        pickedPoints.append(pickedPoint)
        distances.drop(index=pickedPoint, inplace=True)
    return pickedPoints


def assign_bins_to_abs(points, maxBins, exactBins, absDensities):
    """ Returns DF with coordinates of points to which bins can be assigned to inside each ABS. """

    if maxBins is None:
        # assign bins to all points
        return points.index.tolist()
    else:
        absDensities['nBins'] = compute_nbins_in_abs(points, absDensities, maxBins, exactBins)
        # Greedy cover algorithm
        # for each ABS, compute points maximizing cover
        finalPoints = []
        print('Maximizing cover infection area...')
        for densityABS, nBins in tqdm(zip(absDensities.index, absDensities['nBins'])):
            ABSPoints = points.loc[points['abscodi'] == densityABS, :]
            distances = compute_distances(ABSPoints)
            pickedPoints = pick_points_by_distance(distances, nBins)
            finalPoints += pickedPoints
    return finalPoints


def expected_pickup_date(binCapacity, populationDf, absDensities, maskThrowRate, popToThrowRatio):

    def apply_timedelta(daysToFill):
        return (datetime.today() + timedelta(days=daysToFill)).strftime('%d-%m-%Y')

    joinedDensities = absDensities.join(populationDf)
    usablePopulation = joinedDensities['pop'] * popToThrowRatio
    masksPerAbsPerDay = usablePopulation * maskThrowRate
    daysToFillBins = round((joinedDensities['nBins'] * binCapacity) / masksPerAbsPerDay)
    # noinspection PyUnresolvedReferences
    return daysToFillBins.apply(apply_timedelta).rename('pickupDate')


if __name__ == '__main__':

    """ Assigns bins to points defined as coordinates such that the coverage of COVID-19 cases is maximized
        for a given number of bins (locally, for each ABS - Basic Sanitary Area). """

    args = get_arguments()

    # Dades obertes de Catalunya client
    dadesObertesCat = Socrata("analisi.transparenciacatalunya.cat", None)

    casesDf = query_cases(dadesObertesCat, sanitaryRegion=args.sanitaryRegion, daysBefore=args.daysBefore)
    sanitaryRegionABSs = set(casesDf['abscodi'])

    # pick ABSs to cover (i.e. 90% of cases from infection distribution)
    absDensitiesDf = abs_densities(casesDf, args.percCover)
    densityABSs = set(absDensitiesDf.index)

    if args.downloadPoints:
        # Download points to position bins into
        warnings.warn('DOWNLOADING NEW PLACES MIGHT AFFECT GOOGLE MAPS QUOTA.')
        download_process_drugstores(dadesObertesCat, sanitaryRegionABSs, args.apiKey, args.sanitaryRegion)

    # Load points and pick only the ones relevant to current infection densities (of the specified sanitary region)
    pointsDf = pd.read_csv(DATA_PATH + POINTS_NAME + str(args.sanitaryRegion) + '.csv', dtype={'abscodi': str})

    # delete invalid points
    pointsDf = pointsDf.loc[~pointsDf['latitude'].isna(), :]

    pointsToPick = pointsDf['abscodi'].apply(lambda t: t in densityABSs)
    pointsDf = pointsDf.loc[pointsToPick, :]

    # Some ABSs may now not have points becasue of invalid (null) coordinates, so update the used ABSs
    densityABSs = set(pointsDf['abscodi'])
    absDensitiesDf = absDensitiesDf.loc[densityABSs, :].sort_values(by='infectionDensity', ascending=False)

    # assign bins to points inside of the chosen ABSs
    print('Assigning bins to relevant points...')
    pointsIDs = assign_bins_to_abs(pointsDf, args.maxbins, args.exactBins, absDensitiesDf)
    pointsAssigned = pointsDf.loc[pointsIDs, ['direction', 'latitude', 'longitude', 'abscodi']]

    if args.cleanPopulation:
        clean_pop()
    population = pd.read_csv(DATA_PATH + POPULATION_DATA_NAME + '.csv', dtype={'abscodi': object})
    population.set_index('abscodi', inplace=True)

    print('Computing expected bin pickup dates...')
    pickupDates = expected_pickup_date(args.binCapacity, population, absDensitiesDf, args.maskThrowRate,
                                       args.popToThrowRatio)

    pointsAssigned = pointsAssigned.join(pickupDates, on='abscodi')
    
    pointsAssigned.to_csv(OUTPUT_PATH + POINTS_PICKED_LIST_NAME + '.csv', index=False)

    # generate map
    pointsAssigned.loc[:, 'partInfectionDensity'] = None
    for ABS in densityABSs:
        partInfectionDensity = absDensitiesDf.loc[ABS, 'partInfectionDensity']
        pointsAssigned.loc[pointsAssigned['abscodi'] == ABS, 'partInfectionDensity'] = partInfectionDensity

    gmap = gmplot.GoogleMapPlotter(lat=41.4036299, lng=2.1721671, zoom=12, apikey=args.apiKey)
    gmap.scatter(pointsAssigned.loc[:, 'latitude'],
                 pointsAssigned.loc[:, 'longitude'],
                 color='cornflowerblue')
    gmap.heatmap(pointsAssigned.loc[:, 'latitude'],
                 pointsAssigned.loc[:, 'longitude'],
                 radius=40,
                 weights=pointsAssigned.loc[:, 'partInfectionDensity'] * 20,
                 gradient=[(0, 0, 255, 0), (0, 255, 0, 0.9), (255, 0, 0, 1)])

    gmap.draw(OUTPUT_PATH + POINTS_PICKED_MAP_NAME + '.html')

    print("""{} points assigned, see ({}) for a list of 
    directions, ({}) for a map.""".format(len(pointsAssigned.index),
                                          OUTPUT_PATH + POINTS_PICKED_LIST_NAME,
                                          OUTPUT_PATH + POINTS_PICKED_MAP_NAME))
