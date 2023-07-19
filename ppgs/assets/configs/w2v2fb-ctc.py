CONFIG = 'w2v2fb-ctc'
MODULE = 'ppgs'

INPUT_CHANNELS = 768 #dimensionality of wav2vec2 latents
REPRESENTATION = 'w2v2fb'
MODEL = 'transformer'
NUM_WORKERS=6
EVALUATION_BATCHES = 16

NUM_HIDDEN_LAYERS = 5
MAX_FRAMES = 100000
HIDDEN_CHANNELS = 512

EVALUATION_INTERVAL = 1000

OUTPUT_CHANNELS = 41
LOSS_FUNCTION = 'CTC'

import torch
def _backend_old(predicted_logits: torch.Tensor):
    """predicted_logits are BATCH x DIMS x TIME"""
    for sequence_logits in predicted_logits:
        current_prediction = None
        for timestep in sequence_logits.T:
            timestep_prediction = timestep.argmax()
            if current_prediction is None: # first timestep
                current_prediction = timestep_prediction
            elif timestep_prediction == len(timestep) - 1: # prediction is BLANK
                # assign probability to current prediction instead
                timestep[current_prediction] = timestep[-1] #TODO try summing instead?
            else:
                current_prediction = timestep_prediction
    return predicted_logits[:, :-1, :]

def _backend(predicted_logits: torch.Tensor):
    """predicted_logits are BATCH x DIMS x TIME"""
    predictions = predicted_logits.argmax(dim=1)
    blank_indices = torch.argwhere(predictions == 40)
    for batch, time in blank_indices:
        previous_timestep_max = predictions[batch, time-1]
        predictions[batch, time] = predictions[batch, time-1]
        predicted_logits[batch, previous_timestep_max, time] = predicted_logits[batch, 40, time]
    return predicted_logits[:, :-1, :]

BACKEND = _backend