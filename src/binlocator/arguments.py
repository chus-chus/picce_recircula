import argparse


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def get_arguments():
    parser = argparse.ArgumentParser(description="""Distribute bins so that cover is maximized in districts with
                                                     highest case density""")

    parser.add_argument('--maxbins', type=int, default=None, help='Number of bins to be used.')
    parser.add_argument('--exactBins', type=bool, default=False, help='Should the number of bins used be exact?')
    parser.add_argument('--percCover', type=float, default=1, help='Density of infection cases covered.')
    parser.add_argument('--sanitaryRegion', type=int, default=7803, help='Sanitary Region Code.')
    daysBeforeHelp = 'Number of previous days to account for infections from today.'
    parser.add_argument('--daysBefore', type=int, default=14, help=daysBeforeHelp)
    parser.add_argument('--downloadPoints', type=str2bool, default=False, help='Should points be updated?')
    parser.add_argument('--cleanPopulation', type=str2bool, default=False, help='Is the pop. dataset to be cleaned?')
    parser.add_argument('--binCapacity', type=int, required=True, help='Bin capacity.')
    parser.add_argument('--maskThrowRate', type=float, default=1 / 3, help='# of masks thrown away per person per day.')
    parser.add_argument('--popToThrowRatio', type=float, default=1 / 3,
                        help='Ratio of population expected to use bins.')
    parser.add_argument('--apiKey', type=str, default='', help='Google Maps API Key.')

    return parser.parse_args()
