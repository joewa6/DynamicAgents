# Usage:
#   julia --project=v4 v4/run.jl 100
#   julia --project=v4 v4/run.jl 1000 --ticks 5000 --out v4/results/scan.csv

include("../v3/src/config.jl")
include("../v3/src/genetics.jl")
include("../v3/src/bonds.jl")
include("../v3/src/simulation.jl")

include("src/sampling.jl")
include("src/metrics.jl")
include("src/report.jl")
include("src/scanner.jl")

run_scanner_from_cli(ARGS)
