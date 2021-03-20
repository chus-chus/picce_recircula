""" Computes catalan population per ABS from the data:
 https://analisi.transparenciacatalunya.cat/en/Salut/Registre-central-de-poblaci-del-CatSalut-poblaci-p/ftq4-h9vk

 The dataset must be downloaded and put into DATA_PATH with the name POPULATION_DATA_NAME """

import pandas as pd
import math
from datetime import datetime

from src.binlocator.keys import POPULATION_DATA_NAME, DATA_PATH


def clean_pop():
    def std_abs(ABS):
        nDigits = int(math.log10(ABS)) + 1
        if nDigits == 1:
            return '00' + str(ABS)
        elif nDigits == 2:
            return '0' + str(ABS)
        else:
            return str(ABS)

    population = pd.read_csv(DATA_PATH + POPULATION_DATA_NAME + '.csv')
    cols = ['codi Àrea Bàsica de Saut', 'població oficial']
    population = population.loc[population['any'] == datetime.today().year, cols]
    population = population.rename({'codi Àrea Bàsica de Saut': 'abscodi', 'població oficial': 'pop'}, axis=1)
    population = population.groupby(by='abscodi').sum('pop').reset_index()
    population['abscodi'] = population['abscodi'].apply(std_abs)
    population.to_csv(DATA_PATH + POPULATION_DATA_NAME + '.csv', index=False)
