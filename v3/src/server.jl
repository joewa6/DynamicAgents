using HTTP, JSON3

const SIM = Simulation()
const SIM_LOCK = ReentrantLock()
const RUNNING = Ref(false)
const SPEED = Ref(1)
const FOOD_RATE = Ref(3.0f0)
const MUTATION = Ref(0.15f0)
const TARGET_POP_REF = Ref(TARGET_POP)
const FRAME_DT = 1 / 20

function handle_control(msg::AbstractString)
    isempty(msg) && return
    try
        cmd = JSON3.read(msg)
        t = get(cmd, :type, "")
        if t == "play"
            RUNNING[] = !RUNNING[]
        elseif t == "reset"
            lock(SIM_LOCK) do
                reset!(SIM)
            end
        elseif t == "step"
            lock(SIM_LOCK) do
                tick!(SIM, food_rate=FOOD_RATE[], mutation=MUTATION[],
                      target_pop=TARGET_POP_REF[])
            end
        elseif t == "set"
            haskey(cmd, :speed) && (SPEED[] = Int(cmd[:speed]))
            haskey(cmd, :food_rate) && (FOOD_RATE[] = Float32(cmd[:food_rate]))
            haskey(cmd, :mutation) && (MUTATION[] = Float32(cmd[:mutation]))
            haskey(cmd, :target_pop) && (TARGET_POP_REF[] = Int(cmd[:target_pop]))
        elseif t == "set_init_gene"
            lock(SIM_LOCK) do
                set_init_gene!(
                    SIM,
                    Int(cmd[:gene]),
                    String(cmd[:form]),
                    Float32(cmd[:mean]),
                    Float32(cmd[:std]),
                )
            end
        end
    catch e
        @warn "Bad control message" exception=e
    end
end

function run_sim_loop()
    @info "Sim loop started"
    slow_counter = 0
    while true
        if RUNNING[]
            speed = SPEED[]
            if speed == 0
                lock(SIM_LOCK) do
                    stop_at = time() + FRAME_DT * 0.9
                    while time() < stop_at
                        tick!(SIM, food_rate=FOOD_RATE[], mutation=MUTATION[],
                              target_pop=TARGET_POP_REF[])
                    end
                end
            elseif speed > 0
                lock(SIM_LOCK) do
                    for _ in 1:speed
                        tick!(SIM, food_rate=FOOD_RATE[], mutation=MUTATION[],
                              target_pop=TARGET_POP_REF[])
                    end
                end
            else
                slow_counter += 1
                if slow_counter >= abs(speed)
                    lock(SIM_LOCK) do
                        tick!(SIM, food_rate=FOOD_RATE[], mutation=MUTATION[],
                              target_pop=TARGET_POP_REF[])
                    end
                    slow_counter = 0
                end
            end
            sleep(FRAME_DT)
        else
            slow_counter = 0
            sleep(0.02)
        end
    end
end

function ws_handler(ws)
    @info "Client connected"

    reader = @async try
        for msg in ws
            handle_control(String(msg))
        end
    catch e
        @info "WebSocket reader stopped" exception=e
    end

    try
        while !istaskdone(reader)
            frame = lock(SIM_LOCK) do
                serialise_frame(SIM)
            end
            HTTP.WebSockets.send(ws, frame)
            sleep(FRAME_DT)
        end
    catch e
        @info "Client disconnected" exception=e
    finally
        closed = false
        try
            close(ws)
            closed = true
        catch
        end
        if closed && !istaskdone(reader)
            try
                wait(reader)
            catch
            end
        end
    end
end

function http_handler(req::HTTP.Request)
    path = req.target == "/" ? "/index.html" : req.target
    fpath = normpath(joinpath(@__DIR__, "../frontend", lstrip(path, '/')))
    startswith(fpath, normpath(joinpath(@__DIR__, "../frontend"))) ||
        return HTTP.Response(403, "Forbidden")
    isfile(fpath) || return HTTP.Response(404, "Not found")
    ctype = get(Dict(".html" => "text/html", ".js" => "application/javascript",
                     ".css" => "text/css"), splitext(fpath)[2], "text/plain")
    return HTTP.Response(200, ["Content-Type" => ctype], read(fpath))
end

function stream_handler(http)
    if HTTP.WebSockets.isupgrade(http.message)
        HTTP.WebSockets.upgrade(ws_handler, http)
    else
        HTTP.Handlers.streamhandler(http_handler)(http)
    end
end

function serve(host="0.0.0.0"; port=parse(Int, get(ENV, "PORT", "8000")))
    @async run_sim_loop()
    @info "Open http://localhost:$port - WebSocket on /ws"
    HTTP.listen(stream_handler, host, port)
end
