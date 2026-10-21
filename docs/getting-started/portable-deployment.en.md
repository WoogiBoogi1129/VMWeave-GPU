# Deploying to another cluster

[한국어](portable-deployment.md) | English

This procedure installs VMWeave so that a VM can run a small CUDA program and release
its GPU allocation without PyTorch. Administrators provide Kubernetes, KubeVirt,
the NVIDIA driver, and the container runtime. A fresh GPU installation on a separate
system remains **NOT_RUN**. The baseline below reflects the research environment and
build targets; it is not a support guarantee for every version combination.

See the [local package validation results and untested scope](../development/portable-deployment-validation.md)
(in Korean). Some linked operational guides are currently available only in Korean;
the [HAMi DRA guide](hami-dra.md) is in English.

## Deployment baseline

| Component | Baseline |
|---|---|
| Architecture | Linux amd64 |
| Previously tested environment | Kubernetes v1.37.0, KubeVirt v1.9.0 |
| Hook shim | KubeVirt v1.9.0, digest in `versions.lock.yaml` |
| CUDA / Guest OS | CUDA 12.8.1, cuDNN 9 / Ubuntu 22.04 |
| Classic HAMi | v2.10.0 with this repository's patched library |
| GPU execution | VM and Worker on the same GPU node, local filesystem backing |
| Current limits | One active program per VM; 16 MiB per CUDA copy request |

Administrators provision a GPUProfile and local PV for each GPU node. The system
chart does not create host directories or automatically replace drivers, KubeVirt,
or HAMi. The default GPU smoke program uses sm_70 PTX; run it on the target GPU and
driver to verify compatibility.

## 1. Obtain release artifacts

Latest published version: [v0.5.1 artifacts and verification record](release-v0.5.1.md).
Previous version: [v0.4.0](release-v0.4.0.md).

The [v0.5.1 release lock](../../deploy/releases/v0.5.1.json) lists seven public images
and their digests. Classic HAMi uses `vmweave-hami`; DRA uses `vmweave-hami-dra`.
Operator, Helper, Worker, Hook, and Guest artifacts are shared by both backends.
Do not use the historical Flyt `v1.0.0` images for this deployment.

Obtain the release source in a dedicated directory. Run the following installation
tools and use the CRDs from this checkout:

```sh
git clone --branch v0.5.1 --depth 1 https://github.com/WoogiBoogi1129/VMWeave-GPU.git vmweave-v0.5.1
cd vmweave-v0.5.1
mkdir -p .local
helm pull oci://ghcr.io/woogiboogi1129/charts/vmweave-operator --version 0.5.1 --destination .local
python3 scripts/operator/release-manifest.py \
  --repository ghcr.io/woogiboogi1129 --tag v0.5.1 \
  --source-revision b9767652292179bef82f47be20b633a205d19824 \
  --include-dra --output .local/release-images.json
```

Images and the chart can be retrieved without registry login. The lock generator
checks the revision labels of all seven images, but does not verify cryptographic
provenance. Published release records and digest-pinned values were added to main
after the tag was published; access them through the links above. They are absent
from the tag checkout. The steps below use the generic values examples included in
the tag and the generated `.local/release-images.json`.

## 2. Prepare infrastructure and namespaces

- Verify KubeVirt sidecar hook configuration and QEMU ivshmem support.
- **Classic HAMi:** follow the [patched HAMi image procedure](../../runtime/hami/README.md)
  for a fresh installation or an overlay on an existing installation. For a fresh
  installation, combine cluster-specific HAMi chart v2.10.0 values with this
  repository's overlay. Do not copy an existing-release `--reuse-values` command
  directly into a fresh installation.
- **DRA:** prepare the Driver, DeviceClass, and CDI using the [DRA guide](hami-dra.md).
  The classic HAMi scheduler/device-plugin is not required for a DRA-only GPU.
  When both allocators coexist, assign disjoint GPU UUIDs.
- Check the GPU UUID, runtimeClass, and scheduler name for your backend.
- Create namespaces and place any required registry Secrets in each namespace.

```sh
kubectl create namespace vmweave-system
kubectl create namespace team-a
python3 scripts/operator/preflight.py --namespace team-a --node YOUR_GPU_NODE \
  --runtime-class nvidia --output .local/preflight.json
```

This preflight command targets classic HAMi. For DRA, add
`--backend hami-dra --device-class vmweave-hami-dra --gpu-uuid YOUR_GPU_UUID`.

The tool does not change the cluster. `API_CHECKS_PASS` means the API checks passed;
host permissions, drivers, image pulls, GPU execution, and the output's `unverified`
items require separate validation. Add `--tls-mode certManager` when using cert-manager.

## 3. Configure values and certificates

Copy the [existing Secret example](../../deploy/examples/portable/values.json) or
[cert-manager example](../../deploy/examples/portable/cert-manager-values.json) to
`.local/portable-values.json`. Set the Operator repository/digest and namespaces.

`imagePullSecrets` applies to the Operator in the system namespace.
`workloads.imagePullSecrets` applies to Workers and prepare/reclaim Helpers in each
workload namespace. The Hook runs inside the KubeVirt launcher, so configure
Guest/Hook registry Secrets in the VM's `spec.template.spec.imagePullSecrets`.
Secrets are not shared across namespaces.

### Existing Secret

The following tool can generate development certificates. Use your organization's
CA for production. If you change the release name or namespace, update certificate
DNS names accordingly.

```sh
python3 scripts/operator/tls.py --release vmweave --namespace vmweave-system \
  --output .local/portable-tls
kubectl -n vmweave-system create secret tls vmweave-webhook-tls \
  --cert=.local/portable-tls/tls.crt --key=.local/portable-tls/tls.key
python3 scripts/operator/install.py --release vmweave --namespace vmweave-system \
  --values .local/portable-values.json --ca .local/portable-tls/ca.crt
```

For CA rotation, administrators must coordinate the trust transition between the
Secret and Webhook caBundle. Server certificate replacement is picked up through
controller-runtime's file watcher. Uninterrupted admission during renewal must be
validated in the target environment; it is not automatically guaranteed.

### cert-manager

Install cert-manager and cainjector and prepare a usable CA Issuer/ClusterIssuer.
Replace the example issuerRef with your issuer. Do not manage the same TLS Secret
with both cert-manager and manual certificates.

```sh
python3 scripts/operator/install.py --release vmweave --namespace vmweave-system \
  --values .local/portable-values.json
```

The chart creates a Certificate and cainjector injects the CA into the Webhook.
The installation tool validates/applies CRDs, installs Helm resources with Webhook
registration disabled, then registers the Webhook. It waits for Certificate Ready
and CA injection. Scope/mode changes use a separate maintenance procedure.

When using Helm directly, preserve that sequence. Helm's `crds/` directory can
install CRDs initially, but **Helm upgrade does not update CRDs automatically**.
The following example uses cert-manager. For an existing Secret, also set caBundle
in values.

```sh
helm upgrade --install vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/portable-values.json --set webhook.registrationEnabled=false --wait --timeout 5m
helm upgrade vmweave charts/vmweave-operator -n vmweave-system \
  -f .local/portable-values.json --set webhook.registrationEnabled=true --wait --timeout 5m
kubectl -n vmweave-system wait certificate/vmweave-webhook --for=condition=Ready --timeout=180s
```

Use this two-step direct Helm example only for fresh installations. Do not disable
admission arbitrarily on an existing production release. After installation,
check the ValidatingWebhookConfiguration caBundle and perform server-side dry runs
of the relevant custom resources before allowing user workloads.

## 4. Prepare the GPU node and VM

Copy the administrator/user examples from [First VM](first-vm.md).

- Set nodeName, GPU UUID, Worker digest, runtimeClass, and schedulerName.
- Classic HAMi uses `backend: hami` (the default if omitted) and the HAMi scheduler.
  DRA uses `backend: hami-dra`, `draDeviceClass: vmweave-hami-dra`, and
  `schedulerName: default-scheduler`. Follow the [DRA guide](hami-dra.md) for full settings.
- Administrators create the local PV directory and set ownership to the actual QEMU UID/GID.
- Use the same `--uid`/`--gid` when creating the Channel. The default 107:107 is specific
  to the research environment.
- Check PV capacity, available disk space, namespace Pod security policies, and node taints/tolerations.
- Keep the Guest OS root disk separate from the SHM backing PVC.
- Prefer a persistent root PVC. When using containerDisk, preinstall the broker in the image.

Profile approval and PV creation require administrator privileges. Do not grant
Profile approval privileges to workload users. Provision separate Profiles and PVs
when adding nodes.

## 5. Install the Guest runtime

The Guest artifacts image is not a bootable OS. Extract its files on the management
host and transfer them to the VM. Set the image below to the `guest-artifacts`
digest reference from the release lock.

```sh
python3 scripts/operator/export-guest.py --engine docker \
  --image "$GUEST_ARTIFACTS_IMAGE" --output .local/portable-guest
```

The Ubuntu 22.04 Guest needs Python 3, systemd, coreutils, util-linux, and groupadd.
Copy the artifacts to a VM that does not yet have a GPU channel attached, then run:

```sh
sudo sh artifacts/install_guest_broker.sh artifacts
sudo usermod -aG vmweave ubuntu
```

The installer verifies SHA256SUMS and refuses to replace a running broker. For
upgrades, stop active sessions and use the new runtime after a fresh boot.
The source revision is recorded at `/opt/vmweave/source-revision.txt`. Checksums verify
internal image integrity; they do not replace signatures.

Halt the VM, then create a Channel with the same name following the
[VM lifecycle procedure](first-vm.md). On a fresh boot, bootstrap reads the layout
from the config drive. After logging in again, run:

```sh
VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock LD_LIBRARY_PATH=/opt/vmweave/lib \
  /opt/vmweave/bin/guest-gpu-smoke 23 2
```

This program checks GPU memory copies and PTX kernel results. PyTorch is not required.

## 6. Validate installation and reclamation

The execution host needs SSH access to the VM Pod IP. Without direct routing, add
`--virtctl /path/to/virtctl` to tunnel through KubeVirt. Do not store private keys in
results. The automated smoke currently uses the Guest account `ubuntu`.
With the dedicated test VM's Channel Ready, run:

```sh
python3 scripts/operator/smoke-vm.py --namespace team-a --vm gpu-vm \
  --key YOUR_SSH_KEY --output .local/portable-smoke
```

By default, the GPU program runs twice sequentially and leaves the VM running.
Add `--cycle-disposable-vm` to test restart and shutdown on a dedicated test VM.
This can interrupt existing programs and leaves the VM Halted on success.
Check VM/Channel UIDs, the new allocation, and removal of the previous Worker.
On failure, preserve state and do not force deletion. A Stopped Channel and removed
Worker do not independently prove host file deletion; administrators must also
check backing directory reclamation.

## 7. Upgrade, roll back, and uninstall

Follow the [maintenance procedure](../guides/upgrade-uninstall.md).

1. Back up previous values, image digests, CRDs, Profiles, and user resources. Protect private keys separately.
2. Stop active sessions and verify the VM is Halted, the Channel is Stopped or Released, and the Worker is reclaimed.
3. Perform a server-side dry run of the new CRDs, then apply them separately. Stop if stored objects are incompatible.
4. Update Helm, Profile/Channel image references, and Guest artifacts to a compatible release together.
5. Run a smoke test with a new allocation before resuming user workloads.

Helm rollback does not restore CRDs, user Profiles, or Guest files. Restore them
together only when compatible with the previous runtime/CRDs. Follow the atomic
library replacement procedure when replacing or rolling back patched HAMi.
Do not overwrite files mapped by running Workers.

Reclaim and remove user channels normally before uninstalling the Helm release.
Do not assume user VMs, PVCs/PVs, Guest OS data, or Helm `crds/` resources will all
be safely removed automatically. Administrators must review and handle remaining
resources separately. Do not remove finalizers without reclamation evidence.

## Completion criteria

Deployment to another system is validated only after performing a fresh installation,
GPU smoke, VM restart, reclamation, certificate renewal, upgrade, and uninstall
using public/approved images and this guide, and preserving the results.
Code/package validation and actual target-cluster validation remain separate.

For HAMi DRA, follow the [backend installation and lifecycle guide](hami-dra.md).
Keep its allocated GPU set separate from classic HAMi.
