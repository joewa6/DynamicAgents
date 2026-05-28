# World dimensions
const W = 900
const H = 600

# Population
const INIT_AGENTS = 50
const MAX_POP = 200
const TARGET_POP = 80
const INIT_FOOD = 45
const MAX_FOOD = 80

# Energy
const MAX_ENERGY = 100.0f0
const FOOD_ENERGY = 20.0f0
const BASE_DECAY = 0.10f0
const REPRO_ENERGY = 90.0f0
const REPRO_COST = 45.0f0
const FOOD_EAT_R2 = 100.0f0

# Bonds
const MIN_BOND_ROUNDS = 60
const BOND_DECAY_RATE = 0.006f0
const BOND_SCORE_FLOOR = 0.05f0
const BOND_ACTIVE_THRESHOLD = 0.35f0

# Spatial grid
const CELL_SIZE = 80

# Gene layout
const N_GENES = 10

const G_COOP = 1
const G_OPENNESS = 2
const G_SELECTIVITY = 3
const G_FORGIVENESS = 4
const G_KIN_BIAS = 5
const G_SPEED = 6
const G_PERCEPTION = 7
const G_METABOLISM = 8
const G_BOND_THRESH = 9
const G_FERTILITY = 10

const GENE_NAMES = ["coop", "openness", "selectivity", "forgiveness", "kin_bias",
                    "speed", "perception", "metabolism", "bond_thresh", "fertility"]

const GENE_LO = Float32[0, 0, 0, 0, 0, 0.4, 15, 0.05, 0.3, 0.0]
const GENE_HI = Float32[1, 1, 1, 1, 1, 3.5, 90, 0.30, 0.9, 1.0]
