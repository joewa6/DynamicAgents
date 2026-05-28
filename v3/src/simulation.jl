using Random, Statistics

struct BirthRing
    x::Float32
    y::Float32
    born::Int
end

mutable struct Simulation
    alive::BitVector
    x::Vector{Float32}
    y::Vector{Float32}
    vx::Vector{Float32}
    vy::Vector{Float32}
    e::Vector{Float32}
    age::Vector{Int32}
    gen::Vector{Int32}
    pid_a::Vector{Int32}
    pid_b::Vector{Int32}
    uid::Vector{Int32}
    genes::Matrix{Float32}

    fx::Vector{Float32}
    fy::Vector{Float32}
    bonds::BondStore
    rings::Vector{BirthRing}

    init_gene_form::Vector{String}
    init_gene_mean::Vector{Float32}
    init_gene_std::Vector{Float32}
    food_carry::Float32

    round::Int
    uid_counter::Int32
end

function Simulation()
    s = Simulation(
        falses(MAX_POP),
        zeros(Float32, MAX_POP), zeros(Float32, MAX_POP),
        zeros(Float32, MAX_POP), zeros(Float32, MAX_POP),
        zeros(Float32, MAX_POP),
        zeros(Int32, MAX_POP), zeros(Int32, MAX_POP),
        fill(Int32(-1), MAX_POP), fill(Int32(-1), MAX_POP),
        zeros(Int32, MAX_POP),
        Matrix{Float32}(undef, MAX_POP, N_GENES),
        Float32[], Float32[],
        BondStore(), BirthRing[],
        copy(INIT_GENE_FORMS), copy(INIT_GENE_MEAN), copy(INIT_GENE_STD),
        0f0,
        0, Int32(0),
    )
    reset!(s)
    return s
end

function reset!(s::Simulation)
    s.alive .= false
    s.round = 0
    s.uid_counter = Int32(0)
    s.food_carry = 0f0
    empty!(s.bonds.data)
    empty!(s.rings)
    s.fx = rand(Float32, INIT_FOOD) .* W
    s.fy = rand(Float32, INIT_FOOD) .* H
    for _ in 1:INIT_AGENTS
        _spawn!(s, rand(Float32) * W, rand(Float32) * H,
                rand_genes(s.init_gene_form, s.init_gene_mean, s.init_gene_std),
                Int32(-1), Int32(-1), Int32(0))
    end
end

function set_init_gene!(s::Simulation, gene::Int, form::AbstractString,
                        mean::Float32, std::Float32)
    1 <= gene <= N_GENES || return
    span = GENE_HI[gene] - GENE_LO[gene]
    s.init_gene_form[gene] = String(form)
    s.init_gene_mean[gene] = clamp(mean, GENE_LO[gene], GENE_HI[gene])
    s.init_gene_std[gene] = clamp(std, 0f0, span * 0.5f0)
end

function _next_slot(s::Simulation)::Int
    for i in 1:MAX_POP
        s.alive[i] || return i
    end
    return -1
end

function _spawn!(s::Simulation, x::Float32, y::Float32,
                 g::Vector{Float32}, pa::Int32, pb::Int32, gen::Int32)
    slot = _next_slot(s)
    slot == -1 && return
    s.uid_counter += Int32(1)
    s.alive[slot] = true
    s.x[slot] = x
    s.y[slot] = y
    s.vx[slot] = (rand(Float32) - 0.5f0) * g[G_SPEED]
    s.vy[slot] = (rand(Float32) - 0.5f0) * g[G_SPEED]
    s.e[slot] = 30f0 + rand(Float32) * 20f0
    s.age[slot] = 0
    s.gen[slot] = gen
    s.pid_a[slot] = pa
    s.pid_b[slot] = pb
    s.uid[slot] = s.uid_counter
    s.genes[slot, :] .= g
end

function _build_grid(s::Simulation)
    grid = Dict{NTuple{2,Int},Vector{Int}}()
    for i in 1:MAX_POP
        s.alive[i] || continue
        key = (floor(Int, s.x[i] / CELL_SIZE) + 1,
               floor(Int, s.y[i] / CELL_SIZE) + 1)
        push!(get!(grid, key, Int[]), i)
    end
    return grid
end

function tick!(s::Simulation; food_rate::Real=3, mutation::Float32=0.15f0,
               target_pop::Int=TARGET_POP)
    s.round += 1

    s.food_carry += Float32(food_rate)
    n_new = min(floor(Int, s.food_carry), MAX_FOOD - length(s.fx))
    if n_new > 0
        append!(s.fx, rand(Float32, n_new) .* W)
        append!(s.fy, rand(Float32, n_new) .* H)
        s.food_carry -= Float32(n_new)
    end

    grid = _build_grid(s)
    food_eaten = falses(length(s.fx))
    spawn_q = Tuple{Float32,Float32,Vector{Float32},Int32,Int32,Int32}[]
    n_alive = count(s.alive)
    birth_gate = clamp(1f0 - Float32(n_alive) / max(Float32(target_pop), 1f0), 0f0, 1f0)

    for i in 1:MAX_POP
        s.alive[i] || continue
        spd = s.genes[i, G_SPEED]
        perc = s.genes[i, G_PERCEPTION]

        best_fi = 0
        best_d2 = (perc * 3f0)^2
        @inbounds for fi in eachindex(s.fx)
            food_eaten[fi] && continue
            d2 = (s.x[i] - s.fx[fi])^2 + (s.y[i] - s.fy[fi])^2
            d2 < best_d2 && (best_d2 = d2; best_fi = fi)
        end

        if best_fi > 0
            dx = s.fx[best_fi] - s.x[i]
            dy = s.fy[best_fi] - s.y[i]
            d = sqrt(best_d2) + 1f-6
            f = 0.1f0 * spd
            s.vx[i] += dx / d * f
            s.vy[i] += dy / d * f
        else
            s.vx[i] += (rand(Float32) - 0.5f0) * 0.22f0
            s.vy[i] += (rand(Float32) - 0.5f0) * 0.22f0
        end

        actual = sqrt(s.vx[i]^2 + s.vy[i]^2) + 1f-9
        actual > spd && (s.vx[i] *= spd / actual; s.vy[i] *= spd / actual)

        s.x[i] += s.vx[i]
        s.y[i] += s.vy[i]

        if s.x[i] < 2f0
            s.x[i] = 2f0
            s.vx[i] = abs(s.vx[i])
        end
        if s.x[i] > W - 2f0
            s.x[i] = Float32(W - 2)
            s.vx[i] = -abs(s.vx[i])
        end
        if s.y[i] < 2f0
            s.y[i] = 2f0
            s.vy[i] = abs(s.vy[i])
        end
        if s.y[i] > H - 2f0
            s.y[i] = Float32(H - 2)
            s.vy[i] = -abs(s.vy[i])
        end

        @inbounds for fi in eachindex(s.fx)
            food_eaten[fi] && continue
            (s.x[i] - s.fx[fi])^2 + (s.y[i] - s.fy[fi])^2 < FOOD_EAT_R2 || continue
            s.e[i] = min(MAX_ENERGY, s.e[i] + FOOD_ENERGY)
            food_eaten[fi] = true
            break
        end

        cx = floor(Int, s.x[i] / CELL_SIZE) + 1
        cy = floor(Int, s.y[i] / CELL_SIZE) + 1

        for dcx in -1:1, dcy in -1:1
            cell = get(grid, (cx + dcx, cy + dcy), nothing)
            cell === nothing && continue

            for j in cell
                j <= i && continue
                s.alive[j] || continue

                r = min(s.genes[i, G_PERCEPTION], s.genes[j, G_PERCEPTION])
                (s.x[i] - s.x[j])^2 + (s.y[i] - s.y[j])^2 > r^2 && continue

                rand() > s.genes[i, G_OPENNESS] && continue
                rand() > s.genes[j, G_OPENNESS] && continue

                gi = @view s.genes[i, :]
                gj = @view s.genes[j, :]
                gdist = gene_dist(gi, gj)
                gdist > 1f0 - s.genes[i, G_SELECTIVITY] && continue
                gdist > 1f0 - s.genes[j, G_SELECTIVITY] && continue

                ci = s.genes[i, G_COOP]
                cj = s.genes[j, G_COOP]
                delta_i = 0f0
                delta_j = 0f0
                delta_bond = 0f0

                sum_c = ci + cj
                if sum_c > 1.3f0
                    delta_i = 2.5f0
                    delta_j = 2.5f0
                    delta_bond = 0.06f0
                elseif sum_c < 0.7f0
                    delta_i = -3.5f0
                    delta_j = -3.5f0
                    delta_bond = -0.08f0
                else
                    if ci < cj
                        delta_i = 3.0f0
                        delta_j = -4.5f0
                    else
                        delta_j = 3.0f0
                        delta_i = -4.5f0
                    end
                    delta_bond = -0.03f0
                end

                s.e[i] = clamp(s.e[i] + delta_i, 0f0, MAX_ENERGY)
                s.e[j] = clamp(s.e[j] + delta_j, 0f0, MAX_ENERGY)

                if delta_bond < 0
                    forg = (s.genes[i, G_FORGIVENESS] + s.genes[j, G_FORGIVENESS]) * 0.5f0
                    delta_bond *= 1f0 - forg
                end
                update!(s.bonds, i, j, delta_bond, s.round)

                if gdist < 0.2f0
                    kb = (s.genes[i, G_KIN_BIAS] + s.genes[j, G_KIN_BIAS]) * 0.75f0
                    s.e[i] = min(MAX_ENERGY, s.e[i] + kb)
                    s.e[j] = min(MAX_ENERGY, s.e[j] + kb)
                end

                bond = get_or_create!(s.bonds, i, j)
                thresh = max(s.genes[i, G_BOND_THRESH], s.genes[j, G_BOND_THRESH])

                if bond.score >= thresh &&
                   bond.rounds >= MIN_BOND_ROUNDS &&
                   s.e[i] >= REPRO_ENERGY &&
                   s.e[j] >= REPRO_ENERGY &&
                   n_alive + length(spawn_q) < MAX_POP

                    fertility = 0.25f0 + 0.5f0 * (
                        s.genes[i, G_FERTILITY] + s.genes[j, G_FERTILITY]
                    ) * 0.5f0
                    rand(Float32) <= fertility * birth_gate || continue

                    child_g = crossover(gi, gj, mutation)
                    s.e[i] -= REPRO_COST
                    s.e[j] -= REPRO_COST

                    ox = clamp(s.x[i] + (rand(Float32) - 0.5f0) * 15f0, 2f0, Float32(W - 2))
                    oy = clamp(s.y[i] + (rand(Float32) - 0.5f0) * 15f0, 2f0, Float32(H - 2))
                    push!(spawn_q, (ox, oy, child_g,
                                    s.uid[i], s.uid[j],
                                    max(s.gen[i], s.gen[j]) + Int32(1)))

                    push!(s.rings, BirthRing(
                        (s.x[i] + s.x[j]) * 0.5f0,
                        (s.y[i] + s.y[j]) * 0.5f0,
                        s.round,
                    ))

                    bond.score *= 0.4f0
                end
            end
        end

        s.e[i] -= BASE_DECAY + s.genes[i, G_METABOLISM] +
                  spd * 0.025f0 + perc * 0.001f0
        s.age[i] += Int32(1)
    end

    any(food_eaten) && (s.fx = s.fx[.!food_eaten]; s.fy = s.fy[.!food_eaten])

    for i in 1:MAX_POP
        s.alive[i] && s.e[i] <= 0f0 && (s.alive[i] = false; remove_agent!(s.bonds, i))
    end

    for (x, y, g, pa, pb, gen) in spawn_q
        _spawn!(s, x, y, g, pa, pb, gen)
    end

    if s.round % 10 == 0
        decay!(s.bonds, s.round)
        filter!(r -> s.round - r.born <= 60, s.rings)
    end
end

function sim_stats(s::Simulation)::Dict{String,Any}
    idx = findall(s.alive)
    n = length(idx)

    base = Dict{String,Any}(
        "pop" => n,
        "food" => length(s.fx),
        "n_bonds" => length(s.bonds.data),
        "avg_energy" => n > 0 ? mean(s.e[idx]) : 0.0,
        "round" => s.round,
    )
    for k in 1:N_GENES
        base[GENE_NAMES[k]] = n > 0 ? mean(s.genes[idx, k]) : 0.0
    end
    return base
end
