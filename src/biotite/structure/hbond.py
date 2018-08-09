# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

"""
This module provides functions for hydrogen bonding calculation.
"""

__author__ = "Daniel Bauer"
__all__ = ["is_hbond", "hbond", "get_hbond_frequency"]

from .geometry import distance, angle
import numpy as np
from .atoms import AtomArrayStack, stack


def hbond(atoms, donor_selection=None, acceptor_selection=None,
          cutoff_dist=2.5, cutoff_angle=120, donor_elements=('O', 'N', 'S'), acceptor_elements=('O', 'N', 'S')):
    """
    Finds hydrogen bonds between atoms1 and atoms2.
    
    The default criteria is: :math:`\\theta > 120deg` and :math
    :math:`\\text(H..Acceptor) < 2.5 A` (Baker and Hubbard, 1984)
    
    Parameters
    ----------
    
    atoms1 : AtomArray or AtomArrayStack
        model(s) used for hydrogen bond search
    donor_selection : AtomArray or AtomArrayStack or None
        slice of atoms to use as donors (optional)
    acceptor_selection : AtomArray or AtomArrayStack or None
        slice of atoms to use as acceptors (optional)
    cutoff_dist: float or int
        The maximal distance between Donor-H..Acceptor to be considered a hydrogen bond
    cutoff_angle: float or int
        The minimal angle between Donor-H..Acceptor to be considered a hydrogen bond  
    donor_elements: tuple of strings
        Elements to be considered as possible donors
    acceptor_elements: tuple of strings
        Elements to be considered as possible acceptors
        
    Returns
    -------
    array : int
        Nx3 matrix containing the indices of every Donor-H..Acceptor interaction that was counted at least once. N is the number
        of found interactions. The format is [[D_index, H_intex, A_index]]
    array : bool
        MxN matrix that shows if an interaction with index N (see above) is present in the model M.
        
    Examples
    --------
    
    Input
    
    >>> struct = load_structure("tests/structure/data/1l2y.pdb")

    >>> triplets, mask = hbond.hbond(struct)
    >>> hbonds_per_model = mask.sum(axis=1)

    >>> plt.plot(range(len(struct)), hbonds_per_model )
    >>> plt.xlabel("Model")
    >>> plt.ylabel("# H-Bonds")
    >>> plt.show()

    
    Output
    
    TODO
        
    

    """

    # Create AtomArrayStacks from AtomArrays
    if not isinstance(atoms, AtomArrayStack):
        atoms = stack([atoms])

    # if no donor/acceptor selections are made, use the full stack
    # and reduce selections with multiple models
    if donor_selection is None:
        donor_selection = np.full(atoms.array_length(), True)
    elif len(donor_selection.shape) > 1:
        donor_selection = donor_selection[0]
    if acceptor_selection is None:
        acceptor_selection = np.full(atoms.array_length(), True)
    elif len(acceptor_selection.shape) > 1:
        acceptor_selection = acceptor_selection[0]

    # Filter donor/acceptor elements
    donor_selection = donor_selection & np.isin(atoms.element, donor_elements)
    acceptor_selection = acceptor_selection & np.isin(atoms.element, acceptor_elements)

    def _get_bonded_hydrogen(atoms, donor_mask, cutoff=1.5):
        """
        Helper function to find indeces of associated hydrogens in atoms for
        all donors in atoms[donor_mask]. The criterium is that the hydrogen
        must be in the same residue and the distance must be smaller then 1.5
        Angstroem.

        """
        hydrogens_mask = atoms.element == 'H'
        donors = atoms[donor_mask]
        donor_hs = []
        for i in range(donors.array_length()):
            donor = donors[i]
            candidate_mask = hydrogens_mask & (atoms.res_id == donor.res_id)
            # print(candidate_mask)
            candidate_distance = distance(donor, atoms[candidate_mask & hydrogens_mask])

            distances = np.full(atoms.array_length(), -1)
            distances[candidate_mask & hydrogens_mask] = candidate_distance
            donor_h_mask = candidate_mask & (distances <= cutoff) & (distances >= 0)
            donor_hs.append(np.where(donor_h_mask)[0])

        return np.array(donor_hs)

    # TODO use BondList if available
    donor_i = np.where(donor_selection)[0]
    acceptor_i = np.where(acceptor_selection)[0]
    donor_hs_i = _get_bonded_hydrogen(atoms[0], donor_selection)
    # print(donor_hs_i)

    # Build an index list containing the D-H..A triplets in correct order for every possible possible hbond
    max_triplets_size = len(donor_i) * len(acceptor_i) * max(map(lambda x: len(x), donor_hs_i))
    triplets = np.zeros(max_triplets_size, dtype=np.int64)
    triplet_idx = 0
    for donor_hs_idx, d_i in enumerate(donor_i):
        for a_i in acceptor_i:
            if d_i != a_i:
                for dh_i in donor_hs_i[donor_hs_idx]:
                    triplets[triplet_idx:triplet_idx+3] = (d_i, dh_i, a_i)
                    triplet_idx += 3
    triplets = triplets[:triplet_idx]


    # Calculate angle and distance on all triplets
    coords = atoms[:, triplets].coord
    distances = distance(coords[:, 1::3], coords[:, 2::3])
    angles = angle(coords[:, 0::3], coords[:, 1::3], coords[:, 2::3])

    # Apply hbond criterion
    cutoff_angle_radian = np.deg2rad(cutoff_angle)
    hbond_mask = (distances <= cutoff_dist) & (angles >= cutoff_angle_radian)

    # Reduce+Reshape output to contain only triplets counted at least once
    is_counted = hbond_mask.any(axis=0)
    triplets = triplets[np.repeat(is_counted, 3)]
    triplets = np.reshape(triplets, (int(len(triplets)/3), 3))
    hbond_mask = hbond_mask[:, is_counted]

    return triplets, hbond_mask



def is_hbond(donor, donor_h, acceptor, cutoff_dist=2.5, cutoff_angle=120):
    """
    True if the angle and distance between donor, donor_h and acceptor
    meets the criteria of a hydrogen bond
    
    The default criteria is: :math:`\\theta > 120deg` and :math
    :math:`\\text(H..Acceptor) < 2.5 A` (Baker and Hubbard, 1984)
    """

    cutoff_angle_rad = np.deg2rad(cutoff_angle)
    theta = angle(donor, donor_h, acceptor)
    dist = distance(donor_h, acceptor)

    return theta > cutoff_angle_rad and dist < cutoff_dist

def get_hbond_frequency(mask):
    """
    Parameters
    ----------
    mask: Array
        Input mask obtained from `hbond.hbond`
    
    Returns
    -------
    The frequency for each hydrogen bond

    
    Examples
    --------
        
    >>> struct = load_structure("tests/structure/data/1l2y.pdb")

    >>> triplets, mask = hbond.hbond(struct)
    >>> freq = hbond.get_hbond_frequency(mask)

    See Also
    --------
    hbond
    """
    return mask.sum(axis=0)/len(mask)
