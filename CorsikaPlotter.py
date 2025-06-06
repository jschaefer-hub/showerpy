import os
import struct
import random
import numpy as np
import pandas as pd
import eventio
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


class CorsikaPlotter:
    """
    A class to load, parse, and visualize CORSIKA simulation data.

    Attributes:
        path_data (str): Path to the directory containing CORSIKA output files.
        cherenkov_photons (pd.DataFrame or None): Parsed Cherenkov photon data.
        particle_tracks (pd.DataFrame or None): Parsed particle track data.
        file_paths (dict): Dictionary storing available file paths for different data types.
    """

    def __init__(self, path_data):
        """
        Initializes the CorsikaPlotter and loads available data.

        Args:
            path_data (str): Path to the directory containing CORSIKA simulation output.
        """
        self.path_data = path_data
        self.cherenkov_photons = None
        self.particle_tracks = None
        
        # Mapping between CORSIKA particle ID and particle name
        self.particle_map = {
            "gamma": 1,
            "electron": 2,
            "positron": 3,
            "muon": 5,
            "antimuon": 6,
            "proton": 14,
            "helium": 402,
            "lithium": 703,
            "beryllium": 904,
            "boron": 1105,
            "carbon": 1206,
            "nitrogen": 1407,
            "oxygen": 1608,
            "fluorine": 1909,
            "neon": 2010,
            "sodium": 2311,
            "magnesium": 2412,
            "aluminium": 2713,
            "silicon": 2814,
            "phosphorus": 3115,
            "sulfur": 3216,
            "chlorine": 3517,
            "argon": 3618,
            "potassium": 3919,
            "calcium": 4020,
            "scandium": 4321,
            "titanium": 4422,
            "vanadium": 4723,
            "chromium": 4824,
            "manganese": 5125,
            "iron": 5626,
        }

        # Dictionary to store full paths of available files
        self.file_paths = {
            "em_data": None,
            "muon_data": None,
            "hadron_data": None,
            "cherenkov_data": None,
        }

        self._check_available_files()

        # Load data into pandas DataFrames
        self.cherenkov_photons = self._parse_cherenkov_data()
        self.particle_tracks = self._parse_particle_data()

    def _check_available_files(self):
        """
        Checks which types of simulation output files are available in the given directory.

        Raises:
            ValueError: If no CORSIKA files are found.
        """
        try:
            files = os.listdir(self.path_data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: Directory '{self.path_data}' not found.")

        file_patterns = {
            "track_em": "em_data",
            "track_mu": "muon_data",
            "track_hd": "hadron_data",
            "cherenkov_iact": "cherenkov_data",
        }

        # Get paths of files
        for file in files:
            full_path = os.path.join(self.path_data, file)
            if os.path.isfile(full_path):
                for key, attr in file_patterns.items():
                    if file.endswith(key):
                        self.file_paths[attr] = full_path

        print("Looking for available files:")
        # Get longest filetype name so everything is printed nicely!
        max_key_length = max(map(len, self.file_paths.keys()))
        
        # Print some output for the user about found files
        for key, value in self.file_paths.items():
            status = f"Found {os.path.basename(value)}" if value else "Not found"
            print(f"\t -> {key.ljust(max_key_length)} : {status}")

        # Raise error if no files are found in provided directory
        if all(value is None for value in self.file_paths.values()):
            raise ValueError("No CORSIKA files found!")

    def _parse_cherenkov_data(self):
        """
        Parses Cherenkov photon data from the CORSIKA output.

        Returns:
            pd.DataFrame: DataFrame containing Cherenkov photon information.

        Raises:
            ValueError: If the Cherenkov data file is missing.
        """
        print("\nParsing Cherenkov photon data")

        if self.file_paths["cherenkov_data"] is None:
            raise ValueError("Cannot parse Cherenkov data as file was not found!")

        f = eventio.IACTFile(self.file_paths["cherenkov_data"])
        event = next(iter(f))

        # Extract telescope position and photon bunches
        # Note: telescope position not interesting if we only have a single one
        telescope_position = pd.DataFrame(f.telescope_positions)
        cherenkov_photons = pd.DataFrame(event.photon_bunches[0])
        cherenkov_photons.columns = [
            "x_impact_cm",
            "y_impact_cm",
            "cos_incident_x",
            "cos_incident_y",
            "time_since_first_interaction_ns",
            "emission_height_asl_cm",
            "photons",
            "wavelength_nm",
        ]

        # Remove incorrectly parsed column
        cherenkov_photons.drop(columns=["photons"], inplace=True)

        return cherenkov_photons

    def _parse_particle_data(self):
        """
        Parses particle track data from simulation output files.

        Returns:
            pd.DataFrame: A DataFrame containing particle track information.
        """
        print("\nParsing particle track data")

        columns = [
            "particle_id",
            "energy_gev",
            "x_start",
            "y_start",
            "z_start",
            "t_start",
            "x_end",
            "y_end",
            "z_end",
            "t_end",
        ]

        particle_tracks_df = pd.DataFrame(columns=columns)

        for particle_file in list(self.file_paths.values())[:-1]:
            if particle_file is None:
                continue

            print(f"\t-> Reading {os.path.basename(particle_file)}")

            tracks = []
            with open(particle_file, "rb") as f:
                # Iterate over the Fortran file and parse data in accordance
                # with the official CORSIKA/EVENTIO Documentation
                while True:
                    marker1_bytes = f.read(4)
                    if len(marker1_bytes) < 4:
                        break

                    marker1 = struct.unpack("i", marker1_bytes)[0]
                    data_bytes = f.read(marker1)
                    if len(data_bytes) < marker1:
                        break

                    marker2_bytes = f.read(4)
                    if len(marker2_bytes) < 4:
                        break
                    marker2 = struct.unpack("i", marker2_bytes)[0]

                    if marker1 != marker2:
                        raise ValueError(f"Fortran record markers do not match: {marker1} vs {marker2}")

                    tracks.append(struct.unpack("10f", data_bytes))

            if not tracks:
                continue

            # Form a pandas dataframe and discard nan entries
            temp_df = pd.DataFrame(tracks, columns=columns).dropna(axis=1, how="all")
            particle_tracks_df = pd.concat([particle_tracks_df, temp_df], ignore_index=True)

        return particle_tracks_df

    def _cartesian_to_polar(self, x, y):
        """Convert Cartesian coordinates (x, y) to polar coordinates (r, theta)."""
        r = np.sqrt(x**2 + y**2) 
        theta = np.arctan2(y, x) 
        return r, theta
    
    def _ring_area(self, r_inner, r_outer):
        """Calculates the area of a ring using inner and outer diameter

        Args:
            r_inner (float): Inner diameter of ring
            r_outer (float): Outer diameter of ring

        Returns:
            float: Area
        """        
        return np.pi*(r_outer**2 - r_inner**2)
    
    def _get_showerstart_height(self):
        # Identify meaningful shower start for plot via z-height distribution
        nparticles, hasl = np.histogram(
            self.particle_tracks["z_start"] * 1e-5, bins=np.arange(0, 40, 1)
        )
        
        # Flip arrays to start from higher altitudes going down
        nparticles = np.flip(nparticles)
        hasl = np.flip(hasl)
        
        # Begin Plot one step prior to when more than 10 particles are involved
        shower_start = hasl[np.argmax(nparticles > 10) - 1]
        return shower_start 
    
    def plot_side_profile(self, ax=None, alpha=0.1, color_dict=None):
        """
        Plots a side profile of the particle tracks with optional color coding.

        Args:
            ax (matplotlib.axes.Axes, optional): Axis object to plot on. Defaults to None.
            alpha (float, optional): Transparency level for plotted tracks. Defaults to 0.1.
            color_dict (dict, optional): Dictionary mapping particle names to colors.
                Example: {"proton": "red", "electron": "blue"}.

        Returns:
            matplotlib.axes.Axes: The axis containing the plot.
        """
        shower_start = self._get_showerstart_height()

        if ax is None:
            _, ax = plt.subplots(figsize=(3, 8))

        # If no color dictionary is provided, plot all particles in black
        if color_dict is None:
            color_dict = {}

        legend_handles = []
        colored_particle_ids = []
        # Iterate over the provided colors and plot those separately
        for particle_name, color in color_dict.items():
            if particle_name not in self.particle_map:
                print(f"Warning: Unknown particle type '{particle_name}', skipping.")
                continue
            
            particle_id = self.particle_map[particle_name]
            colored_particle_ids.append(colored_particle_ids)
            
            subset = self.particle_tracks[self.particle_tracks["particle_id"] == particle_id]
            
            if subset.empty:
                continue
            
            segments = np.array([
                [[row["x_start"] * 1e-5, row["z_start"] * 1e-5],
                [row["x_end"] * 1e-5, row["z_end"] * 1e-5]]
                for _, row in subset.iterrows()
            ])
            
            ax.add_collection(LineCollection(
                segments, color=color, alpha=alpha, linewidth=0.2, label=particle_name, zorder=2
            ))
            
            # Add solid color line for legend
            legend_handles.append(plt.Line2D([0], [0], color=color, lw=2, label=particle_name))
        
        # All other particle types segments will be shown in black
        filtered_df = self.particle_tracks[~self.particle_tracks["particle_id"].isin(colored_particle_ids)].copy()
        all_segments = np.array([
            [[row["x_start"] * 1e-5, row["z_start"] * 1e-5],
            [row["x_end"] * 1e-5, row["z_end"] * 1e-5]]
            for _, row in filtered_df.iterrows()
        ])
        ax.add_collection(LineCollection(
            all_segments, color="black", alpha=alpha, linewidth=0.08, zorder=1
        ))

        
        # Set plot limits and add legend
        ax.set_ylim(0, shower_start)
        if legend_handles:
            ax.legend(handles=legend_handles)
        
        # Set plot limits and add legend
        ax.set_ylim(0, shower_start)

        return ax
        
    def plot_cher_distribution(self, ax=None, nbins=1000, vmax=None):
        """
        Plots the Cherenkov photon distribution on the observation level.

        Args:
            ax (matplotlib.axes.Axes, optional): Axis object to plot on. Defaults to None.
            nbins (int, optional): Number of bins for histogram. Defaults to 1000.
            vmax (float, optional): Maximum value for color scaling.

        Returns:
            matplotlib.axes.Axes: The axis containing the plot.
        """
        if ax is None:
            _, ax = plt.subplots(figsize=(5, 5))

        # Calculate a guestimate for correct color-bar scale based on 
        # percentile containment
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
            
            vmax = photons_per_bin[np.argmin(np.abs(np.array(fractional_containment)-0.999999))]
            
            
        ax.hist2d(
            self.cherenkov_photons["x_impact_cm"] * 1e-5,
            self.cherenkov_photons["y_impact_cm"] * 1e-5,
            bins=nbins,
            vmin=0,
            vmax=vmax,
            cmap="binary",
        )
        ax.set_aspect("equal")

        return ax
    
    def plot_ground_photon_density(self, ax=None, nbins = 200, color = 'black'):
        """Determines and plots the Cherenkov photon density on ground with 
        respect to the radial distance. 

        Args:
            ax (matplotlib.axes.Axes, optional): Axis object to plot on. Defaults to None.
            nbins (int, optional): Number of radial bins. Defaults to 200.
            color (str, optional): Color of plot. Defaults to 'black'.

        Returns:
            matplotlib.axes.Axes: The axis containing the plot.
        """        
        
        if ax is None:
            _, ax = plt.subplots(figsize=(3, 6))
            
            
        # Convert the impact Cartesian coordinates into polar coordinates 
        impact_r, _ = self._cartesian_to_polar(
                        self.cherenkov_photons.x_impact_cm * 1e-2,
                        self.cherenkov_photons.y_impact_cm * 1e-2
        )
        
        # Setup logarithmic bins to calculate the photon density for
        density_bins = np.logspace(
                                    np.log10(1),
                                    np.log10(800), 
                                    nbins
        ).reshape((nbins//2,2))
    
        # Open up lists to store the output 
        photon_density = []
        radial_bin_centre = []
        
        # Loop over all ring bins
        for inner_radius, outer_radius in density_bins:
            
            # Calculate ring area and determine number of photons within it
            area = self._ring_area(inner_radius, outer_radius) 
            n_photons = ((impact_r < outer_radius) & (impact_r >= inner_radius)).sum()
            
            # Calculate photon density
            photon_density.append(n_photons/area)
            
            # Calculate radial centre of the ring bin
            bin_centre = (inner_radius +  outer_radius)/2.
            radial_bin_centre.append(bin_centre)
            
            
        plt.plot(radial_bin_centre, photon_density, c = color)
        plt.xlabel('Radial distance [m]')
        plt.ylabel(r'Photon density [m$^{-2}$]')
        plt.xscale('log')
        plt.xlim(10, 1e3)
        
        return ax
            
    def plot_particle_height_distribution(self, ax=None, color_dict=None):
        
        if ax is None:
            _, ax = plt.subplots(figsize=(7, 4))
        
        # Get the height at which the shower started 
        shower_start = self._get_showerstart_height()
            
        legend_handles = []
        
        #plot distribution of all particles first
        n_particles, bins = np.histogram(self.particle_tracks.z_start,
                                        bins = np.arange(0,shower_start,0.1)*1e5)
        bin_centres = (bins[:-1]+bins[1:])/2.

        ax.plot(bin_centres *1e-5, n_particles, c = 'black')
        legend_handles.append(
            plt.Line2D([0], [0],
            color='black', 
            lw=2,
            label='All particles')
        )
        
        # Now we loop over all of the particle and color combinations that have
        # been provided and plot them separately
        

        if color_dict:
            for particle_name, color in color_dict.items():
                
                # In case the name contains more particles i.e electron+positron
                # We get the subnames
                subnames = particle_name.replace(' ', '').split('+')
                    
                # Stores total number of particles for each color specification
                all_particles = 0
                group_name = ''
                for name in subnames:
                    
                    # Yeah ... check if we even have the particle that have been 
                    # requested
                    if name not in self.particle_map:
                        print(f"Warning: Unknown particle type '{name}'.")
                        raise()
                    
                    # Get the CORSIKA ID
                    particle_id = self.particle_map[name]
                    
                    # Select all entries with this particle ID
                    subset = self.particle_tracks[self.particle_tracks["particle_id"] == particle_id]
                    
                    # Create the histogram 
                    n_particles, bins = np.histogram(subset.z_start,
                                                    bins = np.arange(0,shower_start,0.1)*1e5
                    )
                    
                    # Add number of particles 
                    all_particles += n_particles
                    
                    group_name += name + 's + '
                # Now we are done with all subnames and plot things 
                bin_centres = (bins[:-1]+bins[1:])/2.

                ax.plot(bin_centres *1e-5, all_particles, c = color)
                    
                    # Add solid color line for legend
                legend_handles.append(plt.Line2D([0], [0],
                                    color=color, 
                                    lw=2, 
                                    label=group_name[:-3])
                )
            
        plt.legend(handles=legend_handles)
        plt.ylabel('Number of particles')
        plt.xlabel('Height a.s.l [km]')
        
        return ax