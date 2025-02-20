import os
import eventio
import pandas as pd 
import struct
import numpy as np
import matplotlib.pyplot as plt
# from matplotlib.colors import Normalize, PowerNorm, LogNorm
from matplotlib.collections import LineCollection

class CorsikaPlotter:
    
    def __init__(self, path_data):
        self.path_data = path_data
        
        self.cherenkov_photons = None 
        self.particle_tracks = None
        
        # Stores the full paths of available files, initialized to None
        self.file_paths = {
            "em_data": None,
            "muon_data": None,
            "hadron_data": None,
            "cherenkov_data": None
        }

        self._check_available_files()
        
        # Load data into pandas dataframes
        self.cherenkov_photons = self._parse_cherenkov_data()
        self.particle_tracks = self._parse_particle_data()
        
    
        
    # Check which types of files are available and write the full paths into the
    # file_paths dict
    def _check_available_files(self):
        # List all files in the directory
        try:
            files = os.listdir(self.path_data)
        except FileNotFoundError:
            print(f"Error: The directory '{self.path_data}' was not found.")
            return

        # Iterate through files and update the availability status with full file paths
        for file in files:
            full_path = os.path.join(self.path_data, file)  # Get the full file path
            
            # Ensure the file is not a directory and exists
            if os.path.isfile(full_path):
                if file.endswith('track_em'):
                    self.file_paths["em_data"] = full_path
                
                if file.endswith('track_mu'):
                    self.file_paths["muon_data"] = full_path
                
                if file.endswith('track_hd'):
                    self.file_paths["hadron_data"] = full_path
                
                if file.endswith('cherenkov_iact'):
                    self.file_paths["cherenkov_data"] = full_path

        # Optionally print the results
        print("Looking for available files:")
        
        max_key_length = max(len(key) for key in self.file_paths.keys())  # Find the longest key length
        
        for key, value in self.file_paths.items():
            print(f"\t -> {key.ljust(max_key_length)} : {'Found ' + os.path.basename(value) if value else 'Not found'}")
            
        if all(value is None for value in self.file_paths.values()):
            raise ValueError('No CORSIKA files found!')
        else:
            return 0
    
    def _parse_cherenkov_data(self):
        
        print('\nParsing Cherenkov photon data')
        if self.file_paths['cherenkov_data'] == None:
            raise ValueError('Cannot parse Cherenkov data as file was not found!')
        
        # It is assumed that you are using the provided particletracks input card 
        # for CORSIKA 
        # Properties: one event, one telescope
        # otherwise, this will just get the data for the first event and telescope in the file 
            
        # Open the file and create an iterator
        f = eventio.IACTFile(self.file_paths['cherenkov_data'])
        it = iter(f)
        
        # Get the first event
        event = next(it)

        
        # Extract the telescope position and photon bunches (bunchsize 1)
        telescope_position = pd.DataFrame(f.telescope_positions)
        cherenkov_photons = pd.DataFrame(event.photon_bunches[0])
        cherenkov_photons.columns='x_impact_cm, y_impact_cm, cos_incident_x, cos_incident_y, time_since_first_interaction_ns, emission_height_asl_cm, photons, wavelength_nm'.split(', ')
        
        # remove incorrectly parsed column
        del cherenkov_photons['photons']
        
        return cherenkov_photons
            
    def _parse_particle_data(self):
        """
        Parse particle data from files and return a DataFrame.
        """
        # Initialize an empty DataFrame with the desired columns
        columns = ['particle_id', 'energy_gev', 'x_start', 'y_start', 'z_start', 
                't_start', 'x_end', 'y_end', 'z_end', 't_end']

        
        print('\nParsing particle track data')

        first_iteration = True
        # Loop over particle file types (excluding Cherenkov data)
        for particle_file in list(self.file_paths.values())[:-1]:
            

            if particle_file is None:
                continue
            
            print(f'\t-> Reading {os.path.basename(particle_file)}')
            
            tracks = []
            
            # Read the particle file and extract the data
            with open(particle_file, "rb") as f:
                while True:
                    # 1) Read the first 4-byte record marker
                    marker1_bytes = f.read(4)
                    if len(marker1_bytes) < 4:
                        break  # End of file reached
                    
                    # Convert to integer
                    marker1 = struct.unpack('i', marker1_bytes)[0]

                    # 2) Read the actual data block (should be marker1 bytes long)
                    data_bytes = f.read(marker1)
                    if len(data_bytes) < marker1:
                        break  # Unexpected end of file

                    # 3) Read the trailing 4-byte record marker
                    marker2_bytes = f.read(4)
                    if len(marker2_bytes) < 4:
                        break
                    marker2 = struct.unpack('i', marker2_bytes)[0]

                    # Sanity check (optional)
                    if marker1 != marker2:
                        raise ValueError(
                            f"Fortran record markers do not match: {marker1} vs {marker2}"
                        )

                    # 4) Now interpret the data bytes as 10 floats
                    floats = struct.unpack('10f', data_bytes)
                    tracks.append(floats)
                    
            tracks = np.array(tracks, dtype=np.float64)
 
            # Skip appending if there are no tracks to store
            if tracks.shape[0] == 0:
                continue
            # Create a temporary DataFrame for the current particle data
            temp_df = pd.DataFrame(tracks, columns=columns)
            
            # Drop columns with all NaN values to avoid issues when concatenating
            temp_df = temp_df.dropna(axis=1, how='all')
            
            # Handle the first iteration differently
            if first_iteration:
                # Assign the first temp_df directly to particle_tracks_df
                particle_tracks_df = temp_df
                first_iteration = False
            else:
                # Append the cleaned temporary DataFrame to the main DataFrame
                particle_tracks_df = pd.concat([particle_tracks_df, temp_df], ignore_index=True)

        return particle_tracks_df
        # cherenkov_photons.columns='x_impact, y_impact, cos_incident_x, cos_incident_y, time_since_first_interaction, emission_height_asl, photons, wavelength'.split(', ')

    def plot_side_profile(self, ax=None, max_traces=None, alpha=0.1):
        """
        Optimized version using LineCollection to speed up plotting.
        """

        # Find location at which shower development starts 
        nparticles, hasl = np.histogram(self.particle_tracks['z_start'] * 1e-5,
                                        bins=np.arange(0, 40, 1))

        # Flip arrays to start from higher altitudes going down
        nparticles = np.flip(nparticles)
        hasl = np.flip(hasl)

        # Find shower start location (where nparticles > 10)
        shower_start = hasl[np.where(nparticles > 10)[0][0] - 1]

        # Create figure if no axis provided
        if ax is None:
            _, ax = plt.subplots(figsize=(3, 8))

        if max_traces is None:
            max_traces = len(self.particle_tracks)

        # Extract particle track data up to max_traces
        subset = self.particle_tracks.iloc[:max_traces]

        # Create an array of line segments
        segments = np.array([
            [[row['x_start'] * 1e-5, row['z_start'] * 1e-5],
            [row['x_end'] * 1e-5, row['z_end'] * 1e-5]]
            for _, row in subset.iterrows()
        ])

        # Use LineCollection for efficient plotting
        lc = LineCollection(segments, color='black', alpha=alpha, linewidth=0.08)
        ax.add_collection(lc)

        # Set plot limits
        ax.set_ylim(0, shower_start)

        return ax
    
    def plot_cher_distribution(self, ax = None, nbins = 1000, vmax = None):
        
        if not ax:
            _, ax = plt.subplots(figsize=(5, 5))
        
        if not vmax:
            # Create preliminary histogram to get photon distribution on 2D plane
            # Note: must have same settings as later plot histogram
            nphotons, _, _ = np.histogram2d(self.cherenkov_photons['x_impact_cm']*1e-5, 
                                            self.cherenkov_photons['y_impact_cm']*1e-5,
                                            bins = nbins
            )

            # Now we create a histogram of photons/pixel with wider binning
            (counts, photons_per_bin) = np.histogram(nphotons.flatten(), bins = 300)
            
            total_photons = counts.sum()
            
            fractional_containment = [counts[:index].sum()/total_photons for index in range(len(counts))]

            
            colorbar_max = photons_per_bin[np.argmin(np.abs(np.array(fractional_containment)-0.999999))]
        else: 
            colorbar_max = vmax
        
        # We determine at which photons/pixel we first get zero entries
        # colorbar_max = photons_per_bin[np.where(count<10)[0][0]]
        # print(colorbar_max_new, colorbar_max)
    
    
        ax.hist2d(self.cherenkov_photons['x_impact_cm']*1e-5, 
                   self.cherenkov_photons['y_impact_cm']*1e-5,
                   bins = nbins,
                   vmin = 0,
                   vmax = colorbar_max,
                   cmap='binary',
        )
        # print(colorbar_max)
        
        plt.gca().set_aspect('equal', adjustable='box') 
        return ax    
