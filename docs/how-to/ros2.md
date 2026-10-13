# ROS 2 packages

The template can generate a **ROS 2** project: an `ament_python` package
(rclpy, Python nodes) or an `ament_cmake` package (C++ nodes), built with
**colcon + rosdep**. The standard toolchain (uv/pixi/poetry, ruff/pytest,
docs, Docker, CI) coexists with the ament layout.

## Choosing the distribution

| Distro | Ubuntu | Python | Status |
|--------|--------|--------|--------|
| **Humble** | 22.04 | 3.10 | Recommended — very widely deployed in industry and education; most third-party drivers (LiDAR, cameras, ...) target it |
| **Jazzy** | 24.04 | 3.12 | Current LTS |

ROS 2 does not ship its own Python interpreter: it uses the Ubuntu LTS
default Python, which is why the `.python-version` is pinned per distro.

## Choosing the environment: apt vs pixi

### apt (classic, default)

The official ROS 2 way: install `ros-{{ '<distro>' }}-*` from the ROS apt
repositories, then use `colcon` + `rosdep`. The pure-Python dev tooling
(ruff/pytest) is managed by your chosen package manager (uv,
poetry, or pixi) — one tool for the Python side, one for ROS.

- `package.xml` declares the ROS dependencies; `rosdep install --from-paths .`
  resolves them.
- CI uses [industrial_ci](https://github.com/ros-industrial/industrial_ci)
  (`ros-industrial/industrial_ci@master`), which builds and tests the
  package inside the matching `ros:<distro>` container.
- `Dockerfile.ros2` is based on `ros:<distro>-ros-base`.

### pixi (RoboStack)

RoboStack publishes ROS 2 packages to conda-forge, one channel per distro.
When you pick pixi for the ROS environment, **pixi manages everything** —
the ROS packages *and* the dev tooling — so the package-manager question is
not asked (no uv/poetry alongside):

```sh
pixi init my_ros_ws -c https://prefix.dev/robostack-jazzy -c https://prefix.dev/conda-forge
cd my_ros_ws
pixi add ros-<distro>-rclpy
pixi run rviz2
```

See <https://pixi.prefix.dev/latest/robotics/> for the recommended setup.
In this template, the pixi ROS environment generates a standalone
`pixi.toml` (RoboStack channel `robostack-<distro>`) with `colcon` + the
ament linters as dev dependencies and `[tasks]` for lint/build/test/check.
CI runs `pixi run colcon build` / `pixi run colcon test` (the apt flavour
uses industrial_ci instead). This is the one place a standalone `pixi.toml`
is generated — ordinary `package_manager: pixi` projects keep their pixi
configuration under `[tool.pixi.*]` in `pyproject.toml` (see [Pixi](pixi.md)).

## What a ros2 project includes

- `package.xml` (format 3) with `<depend>rclpy</depend>` (Python) or
  `<depend>rclcpp</depend>` (C++) and the ament test dependencies.
- `ament_python`: `setup.py` + `setup.cfg` + `resource/<name>` marker +
  `<name>/main.py` rclpy node + `<name>/__init__.py` (exports `__version__`)
  + `test/` ament linters (`test_copyright.py`, `test_flake8.py`,
  `test_pep257.py`).
- `ament_cmake`: `CMakeLists.txt` + `src/talker.cpp` + `include/<name>/`.
- The standard toolchain coexists: `pyproject.toml` keeps its
  `[build-system]`/`[project]` (with `requires-python` pinned to the distro
  and no `rclpy` in `dependencies` — package.xml owns the ROS deps),
  `uv.lock`/`pixi.lock`, the standard `Dockerfile`, docs and
  lint/fix tasks all work as usual. C++ packages skip `pyproject.toml`/`setup.py`
  (the build is CMake).
- `Dockerfile.ros2` (apt or pixi flavour) and a ROS-aware devcontainer
  (with the `ms-iot.vscode-ros` extension).
- `.python-version` pinned to the distro's Python (3.10 / 3.12).
- CI: `industrial_ci` (apt) or `setup-pixi` + colcon (pixi).
- The `test`/`build`/`check` tasks drive colcon (via justfile for apt, or
  pixi's `[tasks]` in `pixi.toml` for the pixi ROS environment).
