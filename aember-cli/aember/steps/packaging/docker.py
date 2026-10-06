import subprocess


def get_running_container_image() -> str:
    """
    Detect the image of the current running container by parsing `docker container ls`.
    Assumes only one devcontainer is running in this environment.
    """
    result = subprocess.run(
        ["docker", "container", "ls", "--no-trunc", "--format", "{{.ID}} {{.Image}}"],
        capture_output=True,
        text=True,
        check=True,
    )

    lines = result.stdout.strip().splitlines()
    if not lines:
        raise RuntimeError("No running containers found via 'docker container ls'")

    _, image = lines[0].split(maxsplit=1)
    return image
