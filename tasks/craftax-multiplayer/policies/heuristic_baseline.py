"""Deterministic role-aware Craftax-Coop code policy."""

WALKABLE={"grass","path","sand","gravel","fire_grass","ice_grass","stairs_down","stairs_up","crafting_table","furnace","enchantment_table_fire","enchantment_table_ice"}
DELTAS={"left":(-1,0),"right":(1,0),"up":(0,-1),"down":(0,1)}

def _cells(observation):return [cell for row in observation["local_view"] for cell in row]
def _cell(observation,x,y):return next((c for c in _cells(observation) if c["x"]==x and c["y"]==y),None)

def act(observation:dict)->dict:
    me=observation["self"];agent=me["agent_id"];role=observation["role"];inventory=me["inventory"]
    for mate in observation["teammate_dashboard"]:
        resource=mate["request"]["resource"]
        if mate["agent_id"]!=agent and resource and (getattr_resource(me,resource)>0):return {"kind":f"give_{resource}_to_{mate['agent_id']}"}
    if role=="forager" and any(m["health"]<=5 for m in observation["teammate_dashboard"]) and me["mana"]>=2:return {"kind":"cast_spell"}
    if me["health"]<=3 and me["equipment"]["potions"]["red"]:return {"kind":"drink_potion_red"}
    if me["food"]<=2:return {"kind":"request_food"}
    if me["drink"]<=2:return {"kind":"request_drink"}
    if role=="miner":
        if inventory["diamond"]>=2 and me["equipment"]["pickaxe"]<4:return {"kind":"make_diamond_pickaxe"}
        if inventory["iron"]>=2 and me["equipment"]["pickaxe"]<3:return {"kind":"make_iron_pickaxe"}
        if inventory["stone"]>=2 and me["equipment"]["pickaxe"]<2:return {"kind":"make_stone_pickaxe"}
    if inventory["wood"] and me["equipment"]["sword"]<1:return {"kind":"make_wood_sword"}
    x,y=me["position"];facing=me["facing"];front=_cell(observation,x+DELTAS[facing][0],y+DELTAS[facing][1])
    wanted={"warrior":{"tree","chest","ripe_plant","boss"},"forager":{"tree","ripe_plant","chest","fountain","boss"},"miner":{"tree","stone","coal","iron","diamond","ruby","sapphire","chest","boss"}}[role]
    if front and (front["terrain"] in wanted or front["mobs"]):return {"kind":"do"}
    adjacent=[]
    for direction,(dx,dy) in DELTAS.items():
        cell=_cell(observation,x+dx,y+dy)
        if cell and (cell["terrain"] in wanted or cell["mobs"]):adjacent.append(direction)
    if adjacent:return {"kind":adjacent[0]}
    here=_cell(observation,x,y)
    if here and here["terrain"]=="stairs_down":return {"kind":"descend"}
    if observation["level"]==8:
        target=(24,24)
    else:target=(45,45)
    preferred=[]
    if target[0]!=x:preferred.append("right" if target[0]>x else "left")
    if target[1]!=y:preferred.append("down" if target[1]>y else "up")
    preferred += [d for d in DELTAS if d not in preferred]
    # Role-specific ordering reduces teammate collisions while retaining the shared objective.
    if role=="forager" and len(preferred)>1:preferred[0],preferred[1]=preferred[1],preferred[0]
    for direction in preferred:
        dx,dy=DELTAS[direction];cell=_cell(observation,x+dx,y+dy)
        if cell and cell["terrain"] in WALKABLE and not cell["agents"]:return {"kind":direction}
    return {"kind":"rest"}

def getattr_resource(me:dict,resource:str)->int:
    if resource in ("food","drink"):return int(me[resource])
    return int(me["inventory"].get(resource,0))
