import torch
import ppgs

###############################################################################
# Aggregate batch metric state
###############################################################################


class Metrics:

    def __init__(self, display_suffix):
        self.metrics = [
            Accuracy(display_suffix),
            CategoricalAccuracy(display_suffix),
            Loss(display_suffix),
            JensenShannon(display_suffix),
            TopKAccuracy(display_suffix, 2),
            TopKAccuracy(display_suffix, 3),
            TopKAccuracy(display_suffix, 5)
        ]

    def __call__(self):
        results = {}
        for metric in self.metrics:
            results.update(metric())
        return results

    def reset(self):
        for metric in self.metrics:
            metric.reset()

    def update(self, predicted_logits, target_indices):
        for metric in self.metrics:
            metric.update(predicted_logits, target_indices)


###############################################################################
# Batch metrics
###############################################################################


class Accuracy:

    def __init__(self, display_suffix):
        self.display_suffix = display_suffix
        self.reset()

    def __call__(self):
        return {f'Accuracy/{self.display_suffix}': float((self.true_positives / self.count).cpu())}

    def reset(self):
        self.count = 0
        self.true_positives = 0

    def update(self, predicted_logits, target_indices):
        # Predicted category is the maximum logit
        predicted_indices = predicted_logits.argmax(dim=1)

        # import pdb; pdb.set_trace()

        # Compare to target indices
        self.true_positives += torch.logical_and(predicted_indices == target_indices, target_indices != -100).sum()

        # Update count
        self.count += (target_indices != -100).sum()

class TopKAccuracy:

    def __init__(self, display_suffix: str, k: int):
        self.display_suffix = display_suffix
        self.k = k
        self.reset()

    def __call__(self):
        return {f'Top{self.k}Accuracy/{self.display_suffix}': float((self.correct_in_top_k / self.count))}
    
    def reset(self):
        self.count = 0
        self.correct_in_top_k = 0

    def update(self, predicted_logits, target_indices):
        top_k_indices = torch.topk(predicted_logits, self.k, dim=1).indices
        for i in range(0, len(target_indices)):
            if target_indices[i] in top_k_indices[i]:
                self.correct_in_top_k += 1
            self.count += 1
        


class CategoricalAccuracy:
    
    def __init__(self, display_suffix):
        self.display_suffix = display_suffix
        self.reset()
        self.map = {i: phoneme for i, phoneme in enumerate(ppgs.PHONEME_LIST)}

    def __call__(self):
        if self.totals is not None:
            assert self.totals.shape == self.counts.shape
        else:
            return None
        output = {}
        for i in range(0, self.totals.shape[0]):
            output[f"Accuracy/{self.display_suffix}/{self.map[i]}"] = (self.totals[i] / self.counts[i]).item()
            output[f"Total/{self.display_suffix}/{self.map[i]}"] = self.totals[i].item()
            output[f"Count/{self.display_suffix}/{self.map[i]}"] = self.counts[i].item()
        return output

    def reset(self):
        self.totals = None
        self.counts = None
    
    def update(self, predicted_logits, target_indices):
        """Update per-category accuracy"""

        #Unroll time dimensionality
        if len(predicted_logits.shape) == 3: #handle batched input
            predicted_logits = torch.transpose(predicted_logits, 1, 2) #Batch,Class,Time->Batch,Time,Class
            predicted_logits = torch.flatten(predicted_logits, 0, 1) #Batch,Time,Class->Batch*Time,Class
            target_indices = torch.flatten(target_indices) #Batch,Time->Batch*Time (1D)

        #deal with -100 ignore values
        keep_indices = (target_indices != -100)
        target_indices = target_indices[keep_indices]
        predicted_logits = predicted_logits[keep_indices]

        #convert logits to onehot
        predicted_indices = predicted_logits.argmax(dim=1)
        predicted_onehots = torch.nn.functional.one_hot(predicted_indices, num_classes=predicted_logits.shape[-1])

        #convert targets to onehot
        target_onehots = torch.nn.functional.one_hot(target_indices, num_classes=predicted_logits.shape[-1])

        #update (or set) totals
        marginal_totals = torch.mul(predicted_onehots, target_onehots).sum(dim=0)
        if self.totals is None:
            self.totals = marginal_totals
        else:
            self.totals += marginal_totals

        #update (or set) counts
        marginal_counts = target_onehots.sum(dim=0)
        if self.counts is None:
            self.counts = marginal_counts
        else:
            self.counts += marginal_counts


class Loss:

    def __init__(self, display_suffix):
        self.display_suffix = display_suffix
        self.reset()

    def __call__(self):
        return {f'Loss/{self.display_suffix}': float((self.total / self.count).cpu().numpy())}

    def reset(self):
        self.total = 0.
        self.count = 0

    def update(self, predicted_logits, target_indices):
        """Update the total cross entropy loss"""
        self.total += torch.nn.functional.cross_entropy(
            predicted_logits,
            target_indices,
            reduction='sum')

        # Update count
        self.count += (target_indices != -100).sum()

class JensenShannon:

    def __init__(self, display_suffix):
        self.display_suffix = display_suffix
        self.reset()

    def __call__(self):
        return {f'JSD/{self.display_suffix}': float((self.total / self.count).cpu().numpy())}

    def reset(self):
        self.total = 0.
        self.count = 0

    def update(self, predicted_logits, target_indices):
        """Update the total JSD"""
        
        #Unroll time dimensionality
        if len(predicted_logits.shape) == 3: #handle batched input
            predicted_logits = torch.transpose(predicted_logits, 1, 2) #Batch,Class,Time->Batch,Time,Class
            predicted_logits = torch.flatten(predicted_logits, 0, 1) #Batch,Time,Class->Batch*Time,Class
            target_indices = torch.flatten(target_indices) #Batch,Time->Batch*Time (1D)
        
        #deal with -100 ignore values
        keep_indices = (target_indices != -100)
        target_indices = target_indices[keep_indices]
        predicted_logits = predicted_logits[keep_indices]
        target_onehot = torch.nn.functional.one_hot(target_indices, num_classes=predicted_logits.shape[-1])

        #compute logits for targets
        target_logits = torch.special.logit(target_onehot, eps=1e-5)

        #calculate JSD and update totals
        self.total += jensenShannonDivergence(predicted_logits, target_logits, as_logits=True)
        self.count += (target_indices != -100).sum() #TODO investigate if -100 needs to be used in JSD THE ANSWER IS YES!!

###############################################################################
# Additional Metric Functions
###############################################################################
def jensenShannonDivergence(p_tensor, q_tensor, as_logits=False):
    """Computes the pointwise Jensen Shannon divergence between tensors sampled from P and Q
    Note that p_tensor and q_tensor are both (possibly batched) probability tensors, NOT in the log space
    unless as_logits=True, in which case BOTH p_tensor and q_tensor are taken as probability logits"""
    m_tensor = (p_tensor+q_tensor)/2
    if not as_logits:
        kl_pm = torch.nn.functional.kl_div(torch.log(m_tensor), p_tensor, reduction="none")
        kl_pm = torch.nan_to_num(kl_pm).sum(dim=-1)
        kl_qm = torch.nn.functional.kl_div(torch.log(m_tensor), q_tensor, reduction="none")
        kl_qm = torch.nan_to_num(kl_qm).sum(dim=-1)
    else:
        kl_pm = torch.nn.functional.kl_div(m_tensor, p_tensor, log_target=True, reduction="none")
        kl_pm = torch.nan_to_num(kl_pm).sum(dim=-1)
        kl_qm = torch.nn.functional.kl_div(m_tensor, q_tensor, log_target=True, reduction='none')
        kl_qm = torch.nan_to_num(kl_qm).sum(dim=-1)
    return torch.sqrt((kl_pm+kl_qm)/2).sum(dim=0)


if __name__ == '__main__':
    #show that it is additive
    print(jensenShannonDivergence(torch.tensor([0.30, 0.50, 0.20]),
        torch.tensor([0.36, 0.48, 0.16])))
    print(jensenShannonDivergence(torch.tensor([0.85, 0.5, 0.1]),
        torch.tensor([1.0, 1e-6, 1e-6])))
    print(jensenShannonDivergence(
        torch.tensor([[0.85, 0.5, 0.1], [0.30, 0.50, 0.20]]),
        torch.tensor([[1.0, 1e-6, 1e-6], [0.36, 0.48, 0.16]]),
    ))

    #Show that it handles zero inputs
    print(jensenShannonDivergence(
        torch.tensor([0.0, 9.0, 1.9]),
        torch.tensor([0.0, -9.0, 10.0]),
    ))
    print(jensenShannonDivergence(
        torch.tensor([1e-9, 9.0, 1.9]),
        torch.tensor([1e-9, -9.0+1e-9, 10.0]),
    ))

    JSMetric = JensenShannon('test')
    input_logits = torch.special.logit(torch.tensor([[0.8, 0.15, 0.05]]))
    input_indices = torch.tensor([1])
    JSMetric.update(input_logits, input_indices)
    print(JSMetric.total)

    Top3 = TopKAccuracy('test', 3)
    input_logits0 = torch.special.logit(torch.tensor([[0.55, 0.16, 0.05, 0.1, 0.14]]))
    input_logits1 = torch.special.logit(torch.tensor([[0.2, 0.25, 0.11, 0.35, 0.09]]))
    input_logits = torch.cat([input_logits0, input_logits1])
    input_indices = torch.tensor([1, 4])
    Top3.update(input_logits, input_indices)
    print(Top3.correct_in_top_k, Top3.count)
