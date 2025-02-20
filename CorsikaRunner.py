import random
import os
from astropy import units as u
from attr import s

class CorsikaRunner():
    
    def __init__(self, 
                 path_corsika_executable, 
                 path_input_card_template = 'input_template.inp', 
                 path_data_output = os.getcwd()
    ):
        
        self.path_corsika_executable = path_corsika_executable
        self.path_input_card_template = path_input_card_template
        self.path_data_output = path_data_output
        
        self.path_inputcard = os.path.join(
            os.path.dirname(self.path_corsika_executable), 
            'sim_particletracks.inp'
        )
            
        
        self.current_config = {
            "run_number" : 1,
            "primary_particle" : None,
            "primary_energy" : None,
            "observation_level": None,
            "zenith_angle": None,  
            'seeds': None,        
        }
        
        
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
            "iron": 5626
        }
           
    def configure_run(self,  
        primary_particle, 
        primary_energy, 
        observation_level = 0 *u.m,   
        run_number = 1, 
        zenith_angle = 0 *u.deg, 
        random_seeds = True,
    ):
        
        
        self.current_config['run_number'] = int(run_number)
        self.current_config['primary_particle'] = self._parse_particletype(
            primary_particle
        )
        self.current_config['primary_energy'] = primary_energy.to(u.GeV)
        self.current_config['zenith_angle'] = (zenith_angle.to(u.deg))
        self.current_config['observation_level'] = observation_level.to(u.cm)
        
        if random_seeds:
            self.current_config['seeds'] = self._generate_seeds()
        else: 
            self.current_config['seeds'] = '*' # Comment out seed to fix it
            
        self._generate_inputcard()
        
        return 0
    
    def _generate_inputcard(self):
        
         # Read the template file
        with open(self.path_input_card_template, "r") as f:
            template_content = f.read()
            
        # Replace placeholders
        template_content = template_content.format(
            run_number = self.current_config['run_number'],
            seeds = self.current_config['seeds'],
            primary_particle = self.current_config['primary_particle'],
            primary_energy = self.current_config['primary_energy'].value,
            zenith_angle = self.current_config['zenith_angle'].value,
            observation_level = self.current_config['observation_level'].value,
            output_directory = os.path.join(
                self.path_data_output,
                'sim_'
            )
        )
        
        
        # Write to the output file
        with open(self.path_inputcard , "w") as f:
            f.write(template_content)
            
        return template_content
            
    def _parse_particletype(self, particle_name):
        
        # Normalize input (case insensitive)
        particle_name = particle_name.lower().strip()

        # Get the corresponding ID
        particle_id = self.particle_map.get(particle_name, None)
        
        if particle_id == None: 
            raise ValueError(f"Unknown primary particle name")
            
        return self.particle_map.get(particle_name, None)
              
    def _generate_seeds(self):
        # Generate unique SEED values
        seed_min, seed_max = 10**7, 10**9  
        second_number_min, second_number_max = 100, 1000  
        seeds = "\n".join([
            f"SEED    {random.randint(seed_min, seed_max)}    {random.randint(second_number_min, second_number_max)}    0     seed for random number sequence {i+1}"
            for i in range(4)
        ])
        return seeds

    def run_simulation(self):
        
        _current_path = os.getcwd()
        
        os.chdir(os.path.dirname(self.path_corsika_executable))
        
        print("Starting CORSIKA simulation (This may take a few minutes)...")
        os.system(f"{self.path_corsika_executable} < {self.path_inputcard} > {self.path_data_output}/corsika_output.log")
        print(f"\nSimulation completed. Check {self.path_data_output}/corsika_output.log for details.")
        
        os.chdir(_current_path)
        