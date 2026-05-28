# Start Julia with multiple threads for best performance:
#   julia --threads=auto run.jl

include("src/config.jl")
include("src/genetics.jl")
include("src/bonds.jl")
include("src/simulation.jl")
include("src/serialiser.jl")
include("src/server.jl")

serve()
