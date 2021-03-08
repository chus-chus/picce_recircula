import argparse
import warnings
import pandas as pd

from sodapy import Socrata
from datetime import datetime, timedelta
from tqdm import tqdm
from geopy.geocoders import Nominatim

POINTS_PATH = './data/binPoints.csv'
INCOMPLETE_POINTS_PATH = './data/incompletePoints.csv'
NOMINATIM_EMAIL = 'jesus.maria.antonanzas@estudiantat.upc.edu'

# ABS
# https://catsalut.gencat.cat/web/.content/minisite/catsalut/proveidors_professionals/registres_catalegs/documents/poblacio-referencia.pdf


def compute_distances(points):
    return 0


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
    for i in range(len(cases)):
        density += cases.iloc[i]['infectionDensity']
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

    print('Fetching COVID-19 cases...')
    for i, row in tqdm(enumerate(resultsCases, start=1)):
        rows.append(pd.DataFrame.from_records(row, index=[i]))

    casesBCN = pd.concat(rows).astype({'numcasos': int})
    casesBCN['data'] = pd.to_datetime(casesBCN['data'])

    return casesBCN


def download_process_drugstores(client, ABSs):
    """ Downloads catalan drug stores, picks the ones from the ABSs of the picked sanitary region
    and searches for their coordinates, saving the info as a CSV for later use. """

    resultsDrugStores = client.get_all("f446-3fny")
    rows = [pd.DataFrame.from_records(next(resultsDrugStores), index=[0])]

    print('Fetching available bin points...')
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
    geolocator = Nominatim(user_agent=NOMINATIM_EMAIL)
    latitudes = []
    longitudes = []
    wrongDirections = []
    # todo improve coordinate searching
    print("Getting points' coordinates from maps...")
    for row in tqdm(drugStoresDf.itertuples()):
        direction = getattr(row, 'direction')
        address = geolocator.geocode(direction)
        if address is None:
            warnings.warn("Some addresses' coordinates could not be found.")
            wrongDirections.append(direction)
            latitudes.append(None)
            longitudes.append(None)
        else:
            latitudes.append(address.latitude)
            longitudes.append(address.longitude)

    drugStoresDf['latitude'] = latitudes
    drugStoresDf['longitude'] = longitudes
    print('Points saved.')
    drugStoresDf.to_csv(POINTS_PATH, index=False)
    warnings.warn('Please manually correct the addresses in {}'.format(INCOMPLETE_POINTS_PATH))
    with open(INCOMPLETE_POINTS_PATH, 'w') as file:
        for listitem in wrongDirections:
            file.write('%s\n' % listitem)


def assign_points_to_abs(drugStoresDf, maxbins):
    """ Returns DF with coordinates of points to which bins can be assigned to inside each ABS. """

    # todo given number of districts to use, density of cases in each district and max number of bins, generate number
    #   of bins for each district (<= num farmacies for now)

    if maxbins is None:
        # assign bins to all points
        pass
    else:
        # Assign number of bins per ABS
        pass
        # Greedy cover algorithm
        # for each ABS
        #   compute distances between points
        #   1) find point furthest from all and pick it
        #   2) find point furthest from the previous
        #   3) find point furthest from the picked points (maximizes the sum of distances)
        #   4) repeat '3' until no more points have to be picked
    return 0


if __name__ == '__main__':

    """ Assigns bins to points defined as coordinates such that the coverage of COVID-19 cases is maximized
        for a given number of bins (locally, for each BCN ABS - Basic Sanitary Area). """

    parser = argparse.ArgumentParser(description="""Distribute bins so that cover is maximized in districts with
                                                 highest case density""")

    parser.add_argument('--maxbins', type=int, default=None, help='Number of bins to be used.')
    parser.add_argument('--percCover', type=float, default=1, help='Density of infection cases covered.')
    parser.add_argument('--sanitaryRegion', type=int, default=7803, help='Sanitary Region Code.')
    parser.add_argument('--daysBefore', type=int, default=14, help='Days to look back cases from.')
    parser.add_argument('--downloadPoints', type=bool, default=False, help='Should points be updated?')

    args = parser.parse_args()

    # Dades obertes de Catalunya client
    dadesObertesCat = Socrata("analisi.transparenciacatalunya.cat", None)

    casesDf = query_cases(dadesObertesCat, sanitaryRegion=args.sanitaryRegion, daysBefore=args.daysBefore)
    sanitaryRegionABSs = set(casesDf['abscodi'])

    # pick ABSs to cover (i.e. 90% of cases from infection distribution)
    absDensitiesDf = abs_densities(casesDf, args.percCover)
    densityABSs = set(absDensitiesDf.index)

    if args.downloadPoints:
        # Download points to position bins into
        download_process_drugstores(dadesObertesCat, sanitaryRegionABSs)

    # Load points and pick only the ones relevant to current infection densities
    pointsDf = pd.read_csv(POINTS_PATH, dtype={'abscodi': str})
    pointsToPick = pointsDf['abscodi'].apply(lambda t: t in densityABSs)
    pointsDf = pointsDf.loc[pointsToPick, :]

    # assign bins to inside of the chosen ABSs
    points = assign_points_to_abs(pointsDf, args.maxbins)

    # return coordinates or / and directions of bins, generate map
