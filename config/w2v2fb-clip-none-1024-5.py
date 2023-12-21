MODULE = 'ppgs'

# Configuration name
CONFIG = 'w2v2fb-clip-none-1024-5'

# Dimensionality of input representation
INPUT_CHANNELS = 768

# Input representation
REPRESENTATION = 'w2v2fb'

NUM_HIDDEN_LAYERS = 5
HIDDEN_CHANNELS = 1024
MAX_TRAINING_FRAMES = 125000

# Clipping parameters
CLIPPING_NORM_TYPE = 1.0
import torch
CLIPPING_THRESHOLD = torch.inf
USE_AUTOCLIP = False
