#!/usr/bin/env python3

"""
Created on 12 Sep. 2022
"""

__author__ = "Nicolas JEANNE"
__copyright__ = "GNU General Public License"
__email__ = "jeanne.n@chu-toulouse.fr"
__version__ = "2.0.0"

import argparse
import logging
import os
import re
import sys

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib import rcParams
import seaborn as sns
import yaml


def create_log(log_path, level, out_dir):
    """Create the log as a text file and as a stream.

    :param log_path: the path of the log.
    :type log_path: str
    :param level: the level og the log.
    :type level: str
    :param out_dir: the results directory path.
    :type out_dir: str
    """
    os.makedirs(out_dir, exist_ok=True)
    if not log_path:
        log_path = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(__file__))[0]}.log")
    log_level_dict = {"DEBUG": logging.DEBUG,
                      "INFO": logging.INFO,
                      "WARNING": logging.WARNING,
                      "ERROR": logging.ERROR,
                      "CRITICAL": logging.CRITICAL}

    log_level = log_level_dict["INFO"]
    if level:
        log_level = log_level_dict[args.log_level]

    if os.path.exists(log_path):
        os.remove(log_path)

    logging.basicConfig(format="%(asctime)s %(levelname)s:\t%(message)s",
                        datefmt="%Y/%m/%d %H:%M:%S",
                        level=log_level,
                        handlers=[logging.FileHandler(log_path), logging.StreamHandler()])
    logging.info(f"version: {__version__}")
    logging.info(f"CMD: {' '.join(sys.argv)}")


def check_optional_args(args_domains, args_embedded_domains, args_residues_distance):
    """Check the combination of optional arguments

    :param args_domains: the domains argument.
    :type args_domains: str
    :param args_embedded_domains: the embedded domains argument.
    :type args_embedded_domains: bool
    :param args_residues_distance: the value of the residues distance argument.
    :type args_residues_distance: int
    """
    if args_embedded_domains and not args_domains:
        logging.warning("--embedded-domains will not be used as the --domains argument is missing.")
    if args_residues_distance != 4 and not args_domains:
        logging.warning(f"--residues-distance {args_residues_distance} will not be used as the --domains argument is "
                        f"missing.")


def get_domains(domains_path, use_embedded):
    """
    Load the domains file and fill in domains that are not covered.

    :param domains_path: the path to the domains file.
    :type domains_path: str
    :param use_embedded: if an embedded domain should be use as a domain or if only the embedding domain should be
    processed.
    :type use_embedded: bool
    :return: the filled-in domains data frame.
    :rtype: pd.Dataframe
    """
    logging.info(f"domains embedded in other domains will{' ' if use_embedded else ' not '}be used in the contacts "
                 f"by domain plot.")
    raw = pd.read_csv(domains_path, sep=",", header=0, names=["domain", "start", "stop", "color"])

    # check for embedded entries
    embedded_raw_idx = []
    previous_stop = 0
    for idx, row in raw.iterrows():
        if row["stop"] < previous_stop:
            embedded_raw_idx.append(idx)
        else:
            previous_stop = row["stop"]

    # update the domains
    data = {"domain": [], "start": [], "stop": [], "color": []}
    expected_start = 1
    previous = {"embedded": False, "domain": None, "stop": None, "color": None}
    for idx, row in raw.iterrows():
        if idx in embedded_raw_idx:  # case of embedded entry
            if use_embedded:
                # modify the previous end of the embedding domain
                data["stop"][-1] = row["start"] - 1
                # register the embedded domain
                data["domain"].append(row["domain"])
                data["start"].append(row["start"])
                data["stop"].append(row["stop"])
                data["color"].append(row["color"])
                # record the end of the domain where the embedded is
                previous["embedded"] = True
                expected_start = row["stop"] + 1
        else:
            if previous["embedded"]:
                # register the end of the domain where the previous was
                data["domain"].append(previous["domain"])
                data["start"].append(expected_start)
                data["stop"].append(previous["stop"])
                data["color"].append(previous["color"])
                expected_start = previous["stop"] + 1
                previous["embedded"] = False
            if row["start"] > expected_start:  # between domains
                # record the undefined domain
                if idx == 0:  # before first domain
                    data["domain"].append(f"before {row['domain']}")
                else:
                    data["domain"].append(f"between {previous['domain']} and {row['domain']}")
                data["start"].append(expected_start)
                data["stop"].append(row["start"] - 1)
                data["color"].append("#cecece")
            # record the current row domain
            data["domain"].append(row["domain"])
            data["start"].append(row["start"])
            data["stop"].append(row["stop"])
            data["color"].append(row["color"])
            previous["domain"] = row["domain"]
            previous["stop"] = row["stop"]
            previous["color"] = row["color"]
            expected_start = row["stop"] + 1

    df = pd.DataFrame(data)
    return df


def get_contacts_analysis_parameters(parameters_path):
    """
    Get the analysis parameters from the previous analysis from trajectories_contacts.py script.

    :param parameters_path: the path to the YAML parameters file.
    :type parameters_path: str
    :return: the parameters.
    :rtype: dict
    """
    with open(parameters_path, "r") as file_handler:
        parameters = yaml.safe_load(file_handler.read())
        logging.info("Parameters used for trajectory contacts search:")
        for p_key, p_value in parameters.items():
            if type(p_value) is dict:
                logging.info(f"\t{p_key}:")
                for p_key_2, p_value_2 in p_value.items():
                    logging.info(f"\t\t{p_key_2}:\t{p_value_2}")
            else:
                logging.info(f"\t{p_key}:\t{p_value}")
    return parameters


def extract_roi(roi_to_extract):
    """
    Extract the start and stop coordinates of the region of interest (roi).

    :param roi_to_extract: the coordinates ot the region of interest, as 100-200 i.e.
    :type roi_to_extract: str
    :raises ArgumentTypeError: is not between 0.0 and 100.0
    :return: the start and stop coordinates of the region of interest.
    :rtype: list
    """
    pattern_roi_to_extract = re.compile("(\\d+)-(\\d+)")
    match_roi_to_extract = pattern_roi_to_extract.search(roi_to_extract)
    if match_roi_to_extract:
        roi_extracted = [int(match_roi_to_extract.group(1)), int(match_roi_to_extract.group(2))]
    else:
        raise argparse.ArgumentTypeError(f"'{roi_to_extract}' argument is malformed, it should be two integers "
                                         f"separated by an hyphen, i.e: '100-200'.")
    return roi_extracted


def get_residues_in_contact(df):
    """
    Reduce the contacts to residues, if 2 residues have multiple atoms in contacts, the pair of atoms with the smallest
    distance will be kept, then create a column with the number of contacts between this 2 residues and finally sort
    the data by position of the ordinates.

    :param df: the contacts from the trajectory analysis.
    :type df: pandas.Dataframe
    :return: the reduced dataframe with the minimal distance value of all the couples of ordinates-abscissas and the
    column with the number of contacts.
    :rtype: pd.Dataframe
    """
    # combinations is used to register the combination of ordinate and abscissa, in this specific order, then
    # select only the value with the minimal contact distance and also the number of contacts for this pair of residues
    combinations = []
    idx_to_remove = []
    combinations_nb_contacts = []
    for _, row in df.iterrows():
        first = f"{row['ordinate position']}{row['ordinate residue']}"
        second = f"{row['abscissa position']}{row['abscissa residue']}"
        if f"{first}_{second}" not in combinations:
            combinations.append(f"{first}_{second}")
            tmp_df = df[(df["ordinate position"] == row["ordinate position"]) & (
                        df["abscissa position"] == row["abscissa position"]) | (
                                    df["abscissa position"] == row["abscissa position"]) & (
                                    df["ordinate position"] == row["ordinate position"])]
            # get the index of the minimal distance
            idx_min = tmp_df[["median distance"]].idxmin()
            # record the index to remove of the other rows of the same combinations positions
            tmp_index_to_remove = list(tmp_df.index.drop(idx_min))
            if tmp_index_to_remove:
                idx_to_remove = idx_to_remove + tmp_index_to_remove
            combinations_nb_contacts.append(len(tmp_df.index))
    df = df.drop(idx_to_remove)
    df["atoms contacts"] = combinations_nb_contacts
    df = df.sort_values(by=["ordinate position"])
    return df


def extract_residues_contacts(path_contacts, roi):
    """
    Extract the contacts from the CSV file residues contacts and filter on the region of interest (if any) for donors
    and acceptors.

    :param path_contacts: the path to the contacts CSV path.
    :type path_contacts: str
    :param roi: the list of the start and end positions of the Region Of Interest.
    :type roi: list
    :return: the filtered contacts.
    :rtype: pd.Dataframe
    """
    # load the contacts file
    df_contacts_all = pd.read_csv(path_contacts, sep=",")
    logging.info(f"{len(df_contacts_all)} atoms contacts in the input data (residues pairs may have multiple atoms "
                 f"contacts).")
    # select the rows of acceptors and donors within the region of interest if any
    roi_text = ""
    ordinate_type = []
    ordinate_position = []
    ordinate_residue = []
    abscissa_position = []
    abscissa_residue = []
    if roi:
        # reduce to the donors region of interest limits
        df_donors = df_contacts_all[df_contacts_all["donor position"].between(roi[0], roi[1])]
        df_acceptors = df_contacts_all[df_contacts_all["acceptor position"].between(roi[0], roi[1])]
        logging.debug(f"{len(df_contacts_all)} atoms contacts in the region of interest.")
        roi_text = f" for donors and acceptors in the region of interest {roi[0]}-{roi[1]}"
        df_contacts_all = pd.concat([df_donors, df_acceptors]).drop_duplicates()
        for _, row in df_contacts_all.iterrows():
            if roi[0] <= row["donor position"] <= roi[1]:
                ordinate_type.append("donor")
                ordinate_position.append(row["donor position"])
                ordinate_residue.append(row["donor residue"])
                abscissa_position.append(row["acceptor position"])
                abscissa_residue.append(row["acceptor residue"])
            else:
                ordinate_type.append("acceptor")
                ordinate_position.append(row["acceptor position"])
                ordinate_residue.append(row["acceptor residue"])
                abscissa_position.append(row["donor position"])
                abscissa_residue.append(row["donor residue"])
    else:
        for _, row in df_contacts_all.iterrows():
            ordinate_type.append("donor")
            ordinate_position.append(row["donor position"])
            ordinate_residue.append(row["donor residue"])
            abscissa_position.append(row["acceptor position"])
            abscissa_residue.append(row["acceptor residue"])
    # loose the notions of donor and acceptor to use ordinate and abscissas
    df_tmp = pd.DataFrame({"contact": df_contacts_all["contact"],
                           "ordinate position": ordinate_position,
                           "ordinate residue": ordinate_residue,
                           "abscissa position": abscissa_position,
                           "abscissa residue": abscissa_residue,
                           "median distance": df_contacts_all["median distance"],
                           "ordinate type": ordinate_type})
    # reduce to residue contacts
    df_residues_contacts = get_residues_in_contact(df_tmp)
    logging.info(f"{len(df_residues_contacts)} extracted residues contacts with {len(df_contacts_all)} atoms "
                 f"contacts{roi_text}.")
    return df_residues_contacts


def heatmap_distances_nb_contacts(df):
    """
    Create a distances and a number of contacts dataframes for the couples ordinates and abscissas.

    :param df: the initial dataframe
    :type df: pd.Dataframe
    :return: the dataframe of distances and the dataframe of the number of contacts.
    :rtype: pd.Dataframe, pd.Dataframe
    """

    # create the dictionaries of distances and number of contacts
    distances = {}
    nb_contacts = {}
    ordinates = []
    abscissas = []
    unique_ordinate_positions = sorted(list(set(df["ordinate position"])))
    unique_abscissa_positions = sorted(list(set(df["abscissa position"])))
    for ordinate_position in unique_ordinate_positions:
        ordinate = f"{ordinate_position}{df.loc[(df['ordinate position'] == ordinate_position), 'ordinate residue'].values[0]}"
        if ordinate not in ordinates:
            ordinates.append(ordinate)
        for abscissa_position in unique_abscissa_positions:
            abscissa = f"{abscissa_position}" \
                       f"{df.loc[(df['abscissa position'] == abscissa_position), 'abscissa residue'].values[0]}"
            if abscissa not in abscissas:
                abscissas.append(abscissa)
            # get the distance
            if abscissa_position not in distances:
                distances[abscissa_position] = []
            dist = df.loc[(df["ordinate position"] == ordinate_position) & (
                        df["abscissa position"] == abscissa_position), "median distance"]
            if not dist.empty:
                distances[abscissa_position].append(dist.values[0])
            else:
                distances[abscissa_position].append(None)
            # get the number of contacts
            if abscissa_position not in nb_contacts:
                nb_contacts[abscissa_position] = []
            contacts = df.loc[(df["ordinate position"] == ordinate_position) & (
                        df["abscissa position"] == abscissa_position), "atoms contacts"]
            if not contacts.empty:
                nb_contacts[abscissa_position].append(contacts.values[0])
            else:
                nb_contacts[abscissa_position].append(None)
    source_distances = pd.DataFrame(distances, index=ordinates)
    source_distances.columns = abscissas
    source_nb_contacts = pd.DataFrame(nb_contacts, index=ordinates)
    source_nb_contacts.columns = abscissas
    return source_distances, source_nb_contacts


def heatmap_contacts(contacts, params, bn, out_dir, output_fmt, lim_roi):
    """
    Create the heatmap of contacts between residues.

    :param contacts: the contacts by residues.
    :type contacts: dict
    :param params: the parameters used in the previous trajectory contacts analysis.
    :type params: dict
    :param bn: the basename.
    :type bn: str
    :param out_dir: the output directory.
    :type out_dir: str
    :param output_fmt: the output format for the heatmap.
    :type output_fmt: str
    :param lim_roi: the region of interest limits for the heatmap.
    :type lim_roi: list
    """
    logging.info("Computing contacts heatmap..")
    # create the distances and number of contacts dataframes to produce the heatmap
    source_distances, source_nb_contacts = heatmap_distances_nb_contacts(contacts)

    # increase the size of the heatmap if too much entries
    factor = int(len(source_distances) / 40) if len(source_distances) / 40 >= 1 else 1
    logging.debug(f"{len(source_distances)} entries, the size of the figure is multiplied by a factor {factor}.")
    rcParams["figure.figsize"] = 15 * factor, 12 * factor
    # create the heatmap
    heatmap = sns.heatmap(source_distances, annot=source_nb_contacts, cbar_kws={"label": "Distance (\u212B)"},
                          linewidths=0.5, xticklabels=True, yticklabels=True)
    heatmap.figure.axes[-1].yaxis.label.set_size(15)
    plot = heatmap.get_figure()
    title = f"Contact residues median distance: {params['sample'] if 'sample' in params else bn}"
    plt.suptitle(title, fontsize="large", fontweight="bold")
    md_duration = f"MD length: {params['MD duration']}. " if "MD duration" in params else ""
    subtitle = f"{md_duration}Count of residues atoms in contact are displayed in the squares."
    if lim_roi:
        subtitle = f"{subtitle}\nRegion Of Interest: {lim_roi[0]} to {lim_roi[1]} ({params['protein length']} " \
                   f"residues in the protein)"
    else:
        subtitle = f"{subtitle}\nRegion Of Interest: 1 to {params['protein length']} (whole protein)"
    if params["frames"]:
        subtitle = f"{subtitle}\n{params['proportion contacts']}% of frames with contacts in frames range " \
                   f"{params['frames']['min']} to {params['frames']['max']}"
    plt.title(subtitle)
    plt.xlabel("Whole protein residues", fontweight="bold")
    plt.ylabel("Region Of Interest residues", fontweight="bold")
    out_path = os.path.join(out_dir, f"heatmap_distances_{bn}.{output_fmt}")
    plot.savefig(out_path)
    # clear the plot for the next use of the function
    plt.clf()
    logging.info(f"\tmedian distance heatmap saved: {out_path}")


def unique_residues_pairs(df_not_unique, col):
    """
    Get the unique residues pairs contacts.

    :param df_not_unique: the dataframe of contacts.
    :type df_not_unique: pd.Dataframe
    :param col: the atoms distances column name.
    :type col: str
    :return: the dataframe of unique residues pairs contacts.
    :rtype: pd.Dataframe
    """
    donor_positions = []
    donor_residues = []
    acceptor_positions = []
    acceptor_residues = []
    nb_contacts = []
    max_atoms_dist = []
    contacts_ids = []
    for donor_position in sorted(list(set(df_not_unique["donor position"]))):
        df_donors = df_not_unique[df_not_unique["donor position"] == donor_position]
        for acceptor_position in sorted(list(set(df_donors["acceptor position"]))):
            df_acceptors = df_donors[df_donors["acceptor position"] == acceptor_position]
            donor_positions.append(donor_position)
            donor_residues.append(df_donors["donor residue"].iloc[0])
            acceptor_positions.append(acceptor_position)
            acceptor_residues.append(df_acceptors["acceptor residue"].iloc[0])
            nb_contacts.append(len(df_acceptors))
            max_atoms_dist.append(max(df_acceptors[col]))
            pair_contacts_ids = []
            for _, row in df_acceptors.iterrows():
                pair_contacts_ids.append(row["contact"])
            contacts_ids.append(" | ".join(pair_contacts_ids))

    df_uniques = pd.DataFrame.from_dict({"donor positions": donor_positions,
                                         "donor residues": donor_residues,
                                         "acceptor positions": acceptor_positions,
                                         "acceptor residues": acceptor_residues,
                                         "atoms contacts": nb_contacts,
                                         "maximum atoms distance": max_atoms_dist,
                                         "contacts ID": contacts_ids})
    return df_uniques


def outliers_contacts(df, res_dist_thr):
    """
    Get the residues pairs contacts above the residues distance contacts, meaning contacts of distant residues.

    :param df: the dataframe of contacts.
    :type df: pd.Dataframe
    :param res_dist_thr: the residues distance threshold.
    :type res_dist_thr: int
    :return: the dataframe of unique residues pairs contacts.
    :rtype: pd.Dataframe
    """
    idx_to_remove_for_residue_distance = []
    for idx, row in df.iterrows():
        if abs(row["ordinate position"] - row["abscissa position"]) < res_dist_thr:
            idx_to_remove_for_residue_distance.append(idx)
    # remove rows with too close distance between the residues
    df.drop(idx_to_remove_for_residue_distance, inplace=True, axis=0)
    # reset the index of the dataframe from 0
    df.reset_index(inplace=True, drop=True)
    logging.debug(f"{len(df)} atoms contacts remaining with a minimal residues distance threshold of {res_dist_thr}.")
    return df


def update_domains(df, domains, path):
    """
    Get the domains for pairs acceptor and donor.

    :param df: the dataframe of unique residues pairs contacts.
    :type df: pd.Dataframe
    :param domains: the domains coordinates.
    :type domains: pd.Dataframe
    :param path: the path of the outliers contacts updated with the domains CSV file.
    :type path: str
    :return: the pairs contacts dataframe updated with the regions.
    :rtype: pd.Dataframe
    """
    donors_regions = [None] * len(df)
    acceptors_regions = [None] * len(df)
    for idx, row_contacts in df.iterrows():
        for _, row_domains in domains.iterrows():
            if row_domains["start"] <= row_contacts["ordinate position"] <= row_domains["stop"]:
                donors_regions[idx] = row_domains["domain"]
            if row_domains["start"] <= row_contacts["abscissa position"] <= row_domains["stop"]:
                acceptors_regions[idx] = row_domains["domain"]
    df.insert(2, "ordinate domains", pd.DataFrame(donors_regions))
    df.insert(5, "abscissa domains", pd.DataFrame(acceptors_regions))
    df.to_csv(path, index=False)
    logging.info(f"Pairs residues contacts updated with domains saved: {path}")
    return df


def acceptors_domains_involved(df, domains, out_dir, bn, roi, fmt, res_dist, params):
    """
    Create the plot of contacts by regions.

    :param df: the dataframe.
    :type df: pd.Dataframe
    :param domains: the domains.
    :type domains: pd.Dataframe
    :param out_dir: the path of the output directory.
    :type out_dir: str
    :param bn: basename for the sample.
    :type bn: str
    :param roi: the region of interest.
    :type roi: str
    :param fmt: the format for the plot.
    :type fmt: str
    :param res_dist: the maximal residues distance in the amino acids chain.
    :type res_dist: int
    :param params: the parameters of the trajectory analysis
    :type params: dict
    """
    data = {}
    for _, row_domains in domains.iterrows():
        tmp = df[df["abscissa domains"] == row_domains["domain"]]
        if not tmp.empty:
            if not row_domains["domain"] in data:
                data[row_domains["domain"]] = 0
            for _, row_tmp in tmp.iterrows():
                data[row_domains["domain"]] += row_tmp["atoms contacts"]
    source = pd.DataFrame.from_dict({"domain": data.keys(), "number of contacts": data.values()})

    # set the seaborn plots style and size
    sns.set_style("darkgrid")
    sns.set_context("poster", rc={"grid.linewidth": 2})
    fig, ax = plt.subplots(figsize=(15, 15))
    sns.barplot(data=source, ax=ax, x="domain", y="number of contacts", color="blue")
    ax.set_xticklabels(source["domain"], rotation=45, horizontalalignment="right")
    ax.set_xlabel(None)
    ax.set_ylabel(f"{'Region Of Interest ' + roi if roi else 'Whole protein'} residues contacts", fontweight="bold")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.text(x=0.5, y=1.1, s=f"{params['sample'] if 'sample' in params else bn}: outliers contacts by domains\nbetween "
                            f"the {'Region Of Interest ' + roi if roi else 'whole protein'} and the whole protein",
            weight="bold", ha="center", va="bottom", transform=ax.transAxes)
    md_duration = f", MD length: {params['MD duration']}." if "MD duration" in params else ""
    ax.text(x=0.5, y=1.0,
            s=f"Maximal atoms distance: {params['maximal atoms distance']} \u212B, minimal angle cut-off "
              f"{params['angle cutoff']}°, minimal residues distance: {res_dist}\n{params['proportion contacts']}% of "
              f"frames with contacts in frames range {params['frames']['min']} to {params['frames']['max']}"
              f"{md_duration}",
            alpha=0.75, ha="center", va="bottom", transform=ax.transAxes)
    path = os.path.join(out_dir, f"outliers_{bn}.{fmt}")
    fig.savefig(path, bbox_inches="tight")
    logging.info(f"Contacts by domain plot saved: {path}")


if __name__ == "__main__":
    descr = f"""
    {os.path.basename(__file__)} v. {__version__}

    Created by {__author__}.
    Contact: {__email__}
    {__copyright__}

    Distributed on an "AS IS" basis without warranties or conditions of any kind, either express or implied.

    From a CSV of the amino acids contacts file and a YAML parameters file, produced by the script 
    trajectories_contacts.py (https://github.com/njeanne/trajectories_contacts), create a heatmap representing the 
    residues contacts.

    If a domains CSV file is used with the option "--domains", a plot and a CSV file of the contacts by domains will be 
    produced. An example of the domains CSV file is provided in data/traj_test_domains.csv
    For this CSV, if some domains are embedded in other domains, they can be displayed in the outputs with the option 
    "--use-embedded".
    """
    parser = argparse.ArgumentParser(description=descr, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", required=True, type=str, help="the path to the output directory.")
    parser.add_argument("-d", "--domains", required=False, type=str, default="",
                        help="the path to the CSV domains file. A comma separated file, the first column is the "
                             "annotation name, the 2nd is the residue start coordinate, the 3rd is the residue end "
                             "coordinate, the last one is the color to apply in hexadecimal format. The coordinate are "
                             "1-indexed.")
    parser.add_argument("-p", "--parameters", required=True, type=str,
                        help="the path to the trajectory contacts analysis parameters (the YAML file in the results "
                             "directory of the trajectory_contacts.py script.")
    parser.add_argument("-i", "--roi", required=False, type=str,
                        help="the donors region of interest coordinates, the format should be two digits separated by "
                             "an hyphen, i.e: '100-200'.")
    parser.add_argument("-f", "--format", required=False, default="svg",
                        choices=["eps", "jpg", "jpeg", "pdf", "pgf", "png", "ps", "raw", "svg", "svgz", "tif", "tiff"],
                        help="the output plots format: 'eps': 'Encapsulated Postscript', "
                             "'jpg': 'Joint Photographic Experts Group', 'jpeg': 'Joint Photographic Experts Group', "
                             "'pdf': 'Portable Document Format', 'pgf': 'PGF code for LaTeX', "
                             "'png': 'Portable Network Graphics', 'ps': 'Postscript', 'raw': 'Raw RGBA bitmap', "
                             "'rgba': 'Raw RGBA bitmap', 'svg': 'Scalable Vector Graphics', "
                             "'svgz': 'Scalable Vector Graphics', 'tif': 'Tagged Image File Format', "
                             "'tiff': 'Tagged Image File Format'. Default is 'svg'.")
    parser.add_argument("-r", "--residues-distance", required=False, type=int, default=4,
                        help="when 2 atoms of different residues are in contact, the minimal distance in number of "
                             "residues that should separate them for a long range interaction. Default is 4 residues, "
                             "the number of residues in an alpha helix.")
    parser.add_argument("-e", "--embedded-domains", required=False, action="store_true",
                        help="for the outliers plot of contacts between a specific domain and the whole protein, use "
                             "the domains embedded in another domain. In example, if the domain 2 is in domain 1, the "
                             "plot will represent the domain 1 as: domain-1 domain-2 domain-1. If this option is not "
                             "used only the domain 1 will be used in the plot.")
    parser.add_argument("-l", "--log", required=False, type=str,
                        help="the path for the log file. If this option is skipped, the log file is created in the "
                             "output directory.")
    parser.add_argument("--log-level", required=False, type=str,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="set the log level. If the option is skipped, log level is INFO.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("input", type=str, help="the donors/acceptors contacts CSV file.")
    args = parser.parse_args()

    # create the logger
    create_log(args.log, args.log_level, args.out)
    check_optional_args(args.domains, args.embedded_domains, args.residues_distance)

    # get the input basename
    basename = os.path.splitext(os.path.basename(args.input))[0]
    # get the Region Of Interest if specified
    if args.roi:
        roi_limits = extract_roi(args.roi)
    else:
        roi_limits = None

    # load the contacts analysis parameters
    try:
        parameters_contacts_analysis = get_contacts_analysis_parameters(args.parameters)
    except ImportError as exc:
        logging.error(exc, exc_info=True)
        sys.exit(1)

    # extract the contacts
    try:
        residues_contacts = extract_residues_contacts(args.input, roi_limits)
    except argparse.ArgumentTypeError as exc:
        logging.error(exc, exc_info=True)
        sys.exit(1)
    except KeyError as exc:
        logging.error(f"\"{args.col_distance}\" column name does not exists in the CSV file.", exc_info=True)
        sys.exit(1)
    except TypeError as exc:
        logging.error(f"\"{args.col_distance}\" column name may refers to a column that is not an atoms distances.",
                      exc_info=True)
        sys.exit(1)

    # get the heatmaps of validated contacts by residues
    heatmap_contacts(residues_contacts, parameters_contacts_analysis, basename, args.out, args.format, roi_limits)

    outliers = outliers_contacts(residues_contacts, args.residues_distance)
    logging.info(f"{len(outliers)} unique residues pairs contacts (<= "
                 f"{parameters_contacts_analysis['maximal atoms distance']} \u212B) with a distance of at least "
                 f"{args.residues_distance} residues{' in the region of interest '+args.roi if args.roi else ''} "
                 f"(residues pair may have multiple atoms contacts).")

    if args.domains:
        # load and format the domains file
        domains_data = get_domains(args.domains, args.embedded_domains)
        # get the outliers contacts
        outliers = update_domains(outliers, domains_data, os.path.join(args.out, f"outliers_{basename}.csv"))

        # by acceptor domain
        acceptors_domains_involved(outliers, domains_data, args.out, basename, args.roi, args.format,
                                   args.residues_distance, parameters_contacts_analysis)