mutable struct BondState
    score::Float32
    rounds::Int32
    last_tick::Int32
    n_pos::Int32
    n_neg::Int32
end

BondState() = BondState(0.3f0, 0, 0, 0, 0)

const BondKey = NTuple{2,Int}

mutable struct BondStore
    data::Dict{BondKey,BondState}
end

BondStore() = BondStore(Dict{BondKey,BondState}())

@inline bkey(i::Int, j::Int) = i < j ? (i, j) : (j, i)

function get_or_create!(bs::BondStore, i::Int, j::Int)::BondState
    get!(bs.data, bkey(i, j), BondState())
end

function update!(bs::BondStore, i::Int, j::Int, delta::Float32, tick::Int)
    b = get_or_create!(bs, i, j)
    b.score = clamp(b.score + delta, 0f0, 1f0)
    b.rounds += Int32(1)
    b.last_tick = Int32(tick)
    delta > 0 ? (b.n_pos += Int32(1)) : (b.n_neg += Int32(1))
end

function decay!(bs::BondStore, tick::Int)
    dead = BondKey[]
    for (key, b) in bs.data
        stale = tick - b.last_tick
        stale > 3 && (b.score *= 1f0 - BOND_DECAY_RATE * stale)
        b.score < BOND_SCORE_FLOOR && push!(dead, key)
    end
    for k in dead
        delete!(bs.data, k)
    end
end

function remove_agent!(bs::BondStore, slot::Int)
    filter!(p -> p.first[1] != slot && p.first[2] != slot, bs.data)
end

active_bonds(bs::BondStore, thresh=BOND_ACTIVE_THRESHOLD) =
    [(k, v) for (k, v) in bs.data if v.score >= thresh]
