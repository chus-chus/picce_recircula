### Recircula Picce Codebase

We are **Picce**!

- Cristina Aguilera (cristina.aguilera.gonzalez@estudiantat.upc.edu)
- Jesus Antonanzas (jesus.maria.antonanzas@estudiantat.upc.edu)
- Irene Josa (irene.josa@upc.edu)
- Paz Ripoll (paz.ripoll@estudiantat.upc.edu)
- Estel Rueda (estel.rueda@upc.edu)

This repository contains some of the software powering our proposal for the Recircula Challenge 2021. 

#### Bin Locator

Automatically places bins around a specified Sanitary Region given parameters such as the % of region infection coverage
of the placements or the maximum number of bins allowed. The coverage of COVID-19 cases is maximized for the given number 
of binsFor now, only farmacies are valid points. It reads, in real time, the number of COVID-19 reports provided by the 
Catalan Government such that the placements are **relevant**.

The granularity of reported infections is by [Basic Sanitary Area](https://catsalut.gencat.cat/web/.content/minisite/catsalut/proveidors_professionals/registres_catalegs/documents/poblacio-referencia.pdf),
and the infections themselves are extracted from [here](https://analisi.transparenciacatalunya.cat/ca/Salut/Registre-de-casos-de-COVID-19-realitzats-a-Catalun/xuwf-dxjd).
The Catalan farmacies are extracted from [here](https://analisi.transparenciacatalunya.cat/Salut/Cat-leg-de-farm-cies-de-Catalunya/f446-3fny).


##### Usage

First, navigate to the desired location and clone the repo:

```
git clone https://github.com/chus-chus/picce_recircula.git
```

Create a virtual environment of your choice and install the required packages:

```
pip3 install requirements.txt
```

An example of running the bin locator could be:

```
python3 ./src/binlocator/main.py --maxbins 100 --percCover 0.8 --exactBins True --daysBefore 14
```

An html map with the best points will be generated in `/images`. You will need a Google Maps API Key to get
a map for non-developer use (without watermarks).

**Available params**:

```
--maxbins: 'Number of bins to be used.' type=int, default=None
--exactBins: 'Should the number of bins used be exact?' type=bool, default=False
--percCover: 'Density of infection cases covered.' type=float, default=1
--sanitaryRegion: 'Sanitary Region Code.' type=int, default=7803
--daysBefore: 'Days to look back cases from.' type=int, default=14
--downloadPoints: 'Should points be updated?' type=bool, default=False
--apiKey: 'Google Maps API Key.' type=str, default=''
```

Do note that downloading new points needs the GMaps API Key to geocode (get coordinates from addresses) and
can consume your Google Cloud Quota, creating extra costs.

[Click here](https://raw.githack.com/chus-chus/picce_recircula/master/images/pointsPickedMap.html) to see an example of
 the map with 100 chosen points, with the color code representing infection density (as of 9/03/2021).