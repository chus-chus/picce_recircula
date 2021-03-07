import argparse
import pandas as pd

from sodapy import Socrata
from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timedelta
from tqdm import tqdm
from geopy.geocoders import Nominatim

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
            break
    return cases.iloc[:i+1]


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


def pick_points(absDensities, client):
    """ Returns DF with coordinates of points to which bins can be assigned to inside each ABS. """
    # drug stores
    # https://analisi.transparenciacatalunya.cat/Salut/Cat-leg-de-farm-cies-de-Catalunya/f446-3fny/data
    resultsDrugStores = dadesObertesCat.get_all("f446-3fny")
    rows = [pd.DataFrame.from_records(next(resultsDrugStores), index=[0])]

    print('Fetching available bin points...')
    for i, row in tqdm(enumerate(resultsDrugStores, start=1)):
        rows.append(pd.DataFrame.from_records(row, index=[i]))

    drugStoresDf = pd.concat(rows).loc[:, ['codi_abs', 'tipus_via', 'nom_via', 'num_via', 'codi_postal']]

    # get drug stores inside the picked ABSs
    pickedABS = set(absDensities.index)
    chosenRows = drugStoresDf['codi_abs'].apply(lambda t: t in pickedABS)
    drugStoresDf = drugStoresDf.loc[chosenRows, :]

    # Clean point directions
    drugStoresDf = drugStoresDf.loc[drugStoresDf['num_via'] != 'S/N', :]

    streetTypes = {'CR': 'Carrer', 'GV': 'Gran Via', 'PL': 'Plaça', 'RB': 'Rambla', 'AV': 'Avinguda',
                   'TS': 'Travessera', 'RD': 'Ronda', 'PS': 'Passeig', 'MO': 'Monestir', 'VI': 'Via', 'PG': 'Passatge',
                   'RI': 'Riera', 'TO': 'Torrent'}
    drugStoresDf['tipus_via'] = drugStoresDf['tipus_via'].apply(lambda t: streetTypes[t])

    drugStoresDf['direction'] = (drugStoresDf['tipus_via'] + " " + drugStoresDf['nom_via'] + " " +
                                 drugStoresDf['num_via'] + ", " + drugStoresDf['codi_postal'] + " Barcelona")
    drugStoresDf = drugStoresDf.drop(['tipus_via', 'nom_via', 'num_via', 'codi_postal'], axis=1)

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! DELETE
    drugStoresDf = drugStoresDf.iloc[1:50]

    # get coordinates from google maps queries
    geolocator = Nominatim(user_agent='jemanac1998@gmail.com')
    latitudes = []
    longitudes = []
    print("Getting points' coordinates from maps...")
    for row in tqdm(drugStoresDf.itertuples()):
        address = geolocator.geocode(getattr(row, 'direction'))
        latitudes.append(address.latitude)
        longitudes.append(address.longitude)

    drugStoresDf['latitude'] = latitudes
    drugStoresDf['longitudes'] = longitudes

    return drugStoresDf


if __name__ == '__main__':

    """ Assigns bins to points defined as coordinates such that the coverage of COVID-19 cases is maximized
        for a given number of bins (locally, for each BCN ABS - Basic Sanitary Area). """

    parser = argparse.ArgumentParser(description="""Distribute bins so that cover is maximized in districts with
                                                 highest case density""")

    parser.add_argument('--maxbins', type=int, default=None, help='Number of bins to be used.')
    parser.add_argument('--percCover', type=float, default=1, help='Density of infection cases covered.')
    parser.add_argument('--sanitaryRegion', type=int, default=7803, help='Sanitary Region Code.')
    parser.add_argument('--daysBefore', type=int, default=14, help='Days to look back cases from.')

    args = parser.parse_args()

    # Dades obertes de Catalunya client
    dadesObertesCat = Socrata("analisi.transparenciacatalunya.cat", None)

    casesDf = query_cases(dadesObertesCat, sanitaryRegion=args.sanitaryRegion, daysBefore=args.daysBefore)

    # pick ABSs to cover (i.e. 90% of cases from infection distribution)
    absDensitiesDf = abs_densities(casesDf, args.percCover)

    # get points to assign bins to inside of the chosen ABSs
    points = pick_points(absDensitiesDf, dadesObertesCat)

    # todo given number of districts to use, density of cases in each district and max number of bins, generate number
    #   of bins for each district (<= num farmacies for now)

    if args.maxbins is None:
        # assign bins to all points
        # maxbins = numfarmacies
        # bin coordinates = farmacies_coordinates
        # return bin coordinates
        pass
    else:
        # get points (farmacies)
        # Farmacies: https://analisi.transparenciacatalunya.cat/Salut/Cat-leg-de-farm-cies-de-Catalunya/f446-3fny/data
        a = 0

        # for each district
        #   (compute haversine dist between farmacies and assign bins so that the distance between all farmacies is
        #   maximum)
        #   distances = compute_distances(farmacies)
        #   assign bins to farmacies

    # todo return coordinates or / and directions of bins, generate map
