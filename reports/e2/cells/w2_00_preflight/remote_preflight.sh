#!/usr/bin/env bash
set -euo pipefail

remote_dir="${1:?remote work directory is required}"
container_name="${2:?container name is required}"
image="${3:?container image is required}"

if docker container inspect "${container_name}" >/dev/null 2>&1; then
  echo "Refusing to alter pre-existing container: ${container_name}" >&2
  exit 70
fi

test -f "${remote_dir}/preflight.py"
code_sha256="$(sha256sum "${remote_dir}/preflight.py" | awk '{print $1}')"
script_sha256="$(sha256sum "${remote_dir}/remote_preflight.sh" | awk '{print $1}')"
image_id="$(docker image inspect "${image}" --format '{{.Id}}')"
image_digest="$(docker image inspect "${image}" --format '{{index .RepoDigests 0}}')"

created=0
stop_benchmark_container() {
  if [[ "${created}" == "1" ]]; then
    docker stop --time 30 "${container_name}" >/dev/null || true
  fi
}
trap stop_benchmark_container EXIT

docker run -d \
  --name "${container_name}" \
  --gpus all \
  --ipc=host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -v "${remote_dir}:/workspace" \
  -w /workspace \
  "${image}" \
  bash -lc 'sleep infinity' >/dev/null
created=1

echo "CODE_SHA256=${code_sha256}"
echo "REMOTE_SCRIPT_SHA256=${script_sha256}"
echo "IMAGE_ID=${image_id}"
echo "IMAGE_DIGEST=${image_digest}"
echo "CONTAINER_NAME=${container_name}"

docker exec "${container_name}" \
  python /workspace/preflight.py run \
    --role dgx_gb10 \
    --device cuda \
    --profile full \
    --output /workspace/dgx_raw.json

test -s "${remote_dir}/dgx_raw.json"
sha256sum "${remote_dir}/dgx_raw.json"
