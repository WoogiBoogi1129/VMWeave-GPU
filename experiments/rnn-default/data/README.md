# MNIST fixture

The fixture contains the first 1,024 training images/labels and first 256 test images/labels
from the public MNIST IDX files served by the PyTorch OSSCI mirror.
`manifest.json` records URLs and SHA256 of the original gzip files.
`mnist.b64` is base64(gzip(train image bytes + train label bytes + test image bytes + test label bytes));
IDX headers are removed. Images are uint8 28×28, labels uint8. Pixel scaling is /255 in the workload.
The fixed subset is for execution/correctness checks, not a representative classification benchmark.
