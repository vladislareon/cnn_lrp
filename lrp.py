"""Class for layer-wise relevance propagation.

Layer-wise relevance propagation for VGG-like networks from PyTorch's Model Zoo.
Implementation can be adapted to work with other architectures as well by adding the corresponding operations.

    Typical usage example:

        model = torchvision.models.vgg16(pretrained=True)
        lrp_model = LRPModel(model)
        r = lrp_model.forward(x)

"""
import torch
from torch import nn
from copy import deepcopy
from src.utils import layers_lookup


class LRPModel(nn.Module):
    """Class wraps PyTorch model to perform layer-wise relevance propagation."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model
        self.model.eval()  # self.model.train() activates dropout / batch normalization etc.!

        # Parse network
        self.layers = self._get_layer_operations()

        # Create LRP network
        self.lrp_layers = self._create_lrp_model()

    def _create_lrp_model(self) -> torch.nn.ModuleList:
        """Method builds the model for layer-wise relevance propagation.

        Returns:
            LRP-model as module list.

        """
        # Clone layers from original model. This is necessary as we might modify the weights.
        layers = deepcopy(self.layers)
        lookup_table = layers_lookup()

        # Run backwards through layers
        for i, layer in enumerate(layers[::-1]):
            try:
                layers[i] = lookup_table[layer.__class__](layer=layer)
            except KeyError:
                message = f"Layer-wise relevance propagation not implemented for " \
                          f"{layer.__class__.__name__} layer."
                raise NotImplementedError(message)

        return layers

    def _get_layer_operations(self) -> torch.nn.ModuleList:
        """Get all network operations and store them in a list.

        This method is adapted to VGG networks from PyTorch's Model Zoo.
        Modify this method to work also for other networks.

        Returns:
            Layers of original model stored in module list.

        """
        layers = torch.nn.ModuleList()
       # layers.append(self.model.cnn1)
        layers.append(self.model.cnn2)
        for layer in self.model.seq1:
              layers.append(layer)
        for layer in self.model.seq2:
              layers.append(layer)
    


        # Parse VGG-16
   #     for layer in self.model.features:
       #     layers.append(layer)

     #   layers.append(self.model.avgpool)
     #   layers.append(torch.nn.Flatten(start_dim=1))

      #  for layer in self.model.classifier:
       #     layers.append(layer)

        return layers

    def forward(self, x: torch.tensor) -> torch.tensor:
        """Forward method that first performs standard inference followed by layer-wise relevance propagation.

        Args:
            x: Input tensor representing an image / images (N, C, H, W).

        Returns:
            Tensor holding relevance scores with dimensions (N, 1, H, W).

        """
        activations = list()

        # Run inference and collect activations.
        with torch.no_grad():
            # Replace image with ones avoids using image information for relevance computation.
            activations.append(torch.ones_like(x))
            #x1 = x.reshape((1, 1, 5000, 1058))
            #x1 = model.cnn1(x1)
            #activations.append(x1)
            #print(x.shape)
            x1 = x.reshape((1, 5000, 1058, 1))
            x1 = self.model.cnn2(x1)
            #print(x1.shape)
            activations.append(x1)
            x1 = x1.reshape((1, 5000, 528, 1))
            for layer in self.model.seq1:
                x1 = layer.forward(x1)
                activations.append(x1)
            x1 = x1.reshape((1, 5000, 528))
            activations[-1] = activations[-1].reshape((1, 5000, 528))
            for layer in self.model.seq2:
                x1 = layer.forward(x1)
                activations.append(x1)
        # Reverse order of activations to run backwards through model
        activations = activations[::-1]
        activations[-1] = activations[-1].reshape((1, 5000, 1058, 1))
        activations = [a.data.requires_grad_(True) for a in activations]

        # Initial relevance scores are the network's output activations
        relevance = torch.softmax(activations.pop(0), dim=-1)  # Unsupervised

        # Perform relevance propagation
        for i, layer in enumerate(self.lrp_layers):
            relevance = layer.forward(activations.pop(0), relevance)
    
        return relevance#.permute(0, 2, 3, 1).sum(dim=-1).squeeze().detach().cpu()
