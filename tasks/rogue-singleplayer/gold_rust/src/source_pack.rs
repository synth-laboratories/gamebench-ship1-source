use crate::{AMULET, ARMOR, FOOD, MAXPACK, POTION, SCROLL, WEAPON};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const ISFOUND: i32 = 0o000020;
const S_SCARE: i32 = 10;

#[derive(Clone, Debug, Serialize, Deserialize)]
struct PackObject {
    id: i32,
    #[serde(rename = "type")]
    obj_type: String,
    which: i32,
    count: i32,
    group: i32,
    flags: i32,
    packch: String,
    pos: Vec<i32>,
}

impl PackObject {
    fn copy_for_leave(&self, id: i32) -> Self {
        Self {
            id,
            obj_type: self.obj_type.clone(),
            which: self.which,
            count: 1,
            group: self.group,
            flags: self.flags,
            packch: self.packch.clone(),
            pos: self.pos.clone(),
        }
    }
}

struct SourcePack {
    pack: Vec<PackObject>,
    level_objects: Vec<PackObject>,
    discarded: Vec<i32>,
    returned: Vec<PackObject>,
    inpack: i32,
    pack_used: [bool; 26],
    amulet: bool,
    next_id: i32,
    last_pick: Option<i32>,
}

impl SourcePack {
    fn new() -> Self {
        Self {
            pack: Vec::new(),
            level_objects: Vec::new(),
            discarded: Vec::new(),
            returned: Vec::new(),
            inpack: 0,
            pack_used: [false; 26],
            amulet: false,
            next_id: 1,
            last_pick: None,
        }
    }

    fn make(
        &mut self,
        obj_type: char,
        which: i32,
        count: i32,
        group: i32,
        flags: i32,
        pos: (i32, i32),
    ) -> PackObject {
        let obj = PackObject {
            id: self.next_id,
            obj_type: obj_type.to_string(),
            which,
            count,
            group,
            flags,
            packch: String::new(),
            pos: vec![pos.0, pos.1],
        };
        self.next_id += 1;
        obj
    }

    fn add_floor(&mut self, obj: PackObject) {
        self.level_objects.insert(0, obj);
    }

    fn add_pack(&mut self, mut obj: PackObject, from_floor: bool) -> &'static str {
        let obj_id = obj.id;
        let obj_type = obj.obj_type.clone();
        let obj_which = obj.which;
        let obj_group = obj.group;
        if obj.obj_type == SCROLL.to_string() && obj.which == S_SCARE && obj.flags & ISFOUND != 0 {
            if from_floor {
                self.detach_level_object(obj.id);
            }
            self.discarded.push(obj.id);
            return "scare_dust";
        }
        if self.pack.is_empty() {
            obj.packch = self.pack_char();
            self.inpack += 1;
            self.pack.push(obj);
        } else {
            let mut lp_index: Option<usize> = None;
            let mut op_index = 0usize;
            while op_index < self.pack.len() {
                if self.pack[op_index].obj_type != obj.obj_type {
                    lp_index = Some(op_index);
                    op_index += 1;
                    continue;
                }
                while self.pack[op_index].obj_type == obj.obj_type
                    && self.pack[op_index].which != obj.which
                {
                    lp_index = Some(op_index);
                    if op_index + 1 == self.pack.len() {
                        break;
                    }
                    op_index += 1;
                }
                if self.pack[op_index].obj_type == obj.obj_type
                    && self.pack[op_index].which == obj.which
                {
                    if is_mult(&self.pack[op_index].obj_type) {
                        if !self.pack_room(from_floor, obj.id) {
                            return "no_room";
                        }
                        self.pack[op_index].count += 1;
                        self.discarded.push(obj.id);
                        lp_index = None;
                        break;
                    }
                    if obj.group != 0 {
                        lp_index = Some(op_index);
                        while self.pack[op_index].obj_type == obj.obj_type
                            && self.pack[op_index].which == obj.which
                            && self.pack[op_index].group != obj.group
                        {
                            lp_index = Some(op_index);
                            if op_index + 1 == self.pack.len() {
                                break;
                            }
                            op_index += 1;
                        }
                        if self.pack[op_index].obj_type == obj.obj_type
                            && self.pack[op_index].which == obj.which
                            && self.pack[op_index].group == obj.group
                        {
                            self.pack[op_index].count += obj.count;
                            self.inpack -= 1;
                            if !self.pack_room(from_floor, obj.id) {
                                return "no_room";
                            }
                            self.discarded.push(obj.id);
                            lp_index = None;
                            break;
                        }
                    } else {
                        lp_index = Some(op_index);
                    }
                }
                break;
            }
            if let Some(index) = lp_index {
                if !self.pack_room(from_floor, obj.id) {
                    return "no_room";
                }
                obj.packch = self.pack_char();
                self.pack.insert(index + 1, obj);
            }
        }
        let last_index = self
            .pack
            .iter()
            .position(|candidate| candidate.id == obj_id);
        if let Some(index) = last_index {
            self.pack[index].flags |= ISFOUND;
            if self.pack[index].obj_type == AMULET.to_string() {
                self.amulet = true;
            }
        } else if let Some(index) = self.pack.iter().position(|candidate| {
            candidate.obj_type == obj_type
                && candidate.which == obj_which
                && candidate.group == obj_group
        }) {
            self.pack[index].flags |= ISFOUND;
            if self.pack[index].obj_type == AMULET.to_string() {
                self.amulet = true;
            }
        }
        "added"
    }

    fn pack_room(&mut self, from_floor: bool, obj_id: i32) -> bool {
        self.inpack += 1;
        if self.inpack > MAXPACK as i32 {
            self.inpack = MAXPACK as i32;
            return false;
        }
        if from_floor {
            self.detach_level_object(obj_id);
        }
        true
    }

    fn leave_pack(&mut self, obj_id: i32, newobj: bool, all_items: bool) -> PackObject {
        let index = self.pack.iter().position(|obj| obj.id == obj_id).unwrap();
        self.inpack -= 1;
        let returned;
        if self.pack[index].count > 1 && !all_items {
            self.last_pick = Some(self.pack[index].id);
            self.pack[index].count -= 1;
            if self.pack[index].group != 0 {
                self.inpack += 1;
            }
            if newobj {
                returned = self.pack[index].copy_for_leave(self.next_id);
                self.next_id += 1;
            } else {
                returned = self.pack[index].clone();
            }
        } else {
            self.last_pick = None;
            if !self.pack[index].packch.is_empty() {
                let pack_index = self.pack[index].packch.as_bytes()[0] - b'a';
                self.pack_used[pack_index as usize] = false;
            }
            returned = self.pack.remove(index);
        }
        self.returned.push(returned.clone());
        returned
    }

    fn pack_char(&mut self) -> String {
        for index in 0..self.pack_used.len() {
            if !self.pack_used[index] {
                self.pack_used[index] = true;
                return ((b'a' + index as u8) as char).to_string();
            }
        }
        panic!("Rogue pack_char exhausted");
    }

    fn to_value(&self) -> Value {
        let pack_used = self
            .pack_used
            .iter()
            .enumerate()
            .filter_map(|(index, used)| {
                if *used {
                    Some((b'a' + index as u8) as char)
                } else {
                    None
                }
            })
            .collect::<String>();
        json!({
            "pack": self.pack,
            "level_objects": self.level_objects,
            "discarded": self.discarded,
            "returned": self.returned,
            "inpack": self.inpack,
            "pack_used": pack_used,
            "amulet": self.amulet,
            "last_pick": self.last_pick,
        })
    }

    fn detach_level_object(&mut self, obj_id: i32) {
        let index = self
            .level_objects
            .iter()
            .position(|obj| obj.id == obj_id)
            .unwrap();
        self.level_objects.remove(index);
    }
}

pub fn source_pack_report() -> Value {
    json!({
        "cases": [
            case_initial_order(),
            case_multi_merge(),
            case_group_merge_and_split(),
            case_pack_overflow(),
            case_scare_scroll_dust(),
            case_leave_all_removes_packch(),
            case_amulet_flag(),
        ]
    })
}

fn case_initial_order() -> Value {
    let mut state = SourcePack::new();
    let food = state.make(FOOD, 0, 1, 0, 0, (0, 0));
    let armor = state.make(ARMOR, 1, 1, 0, 0, (0, 0));
    let mace = state.make(WEAPON, 0, 1, 0, 0, (0, 0));
    let bow = state.make(WEAPON, 2, 1, 0, 0, (0, 0));
    let arrows = state.make(WEAPON, 3, 31, 2, 0, (0, 0));
    for obj in [food, armor, mace, bow, arrows] {
        state.add_pack(obj, false);
    }
    json!({"name": "initial_order", "state": state.to_value()})
}

fn case_multi_merge() -> Value {
    let mut state = SourcePack::new();
    let first = state.make(FOOD, 0, 1, 0, 0, (0, 0));
    let first_id = first.id;
    let second = state.make(FOOD, 0, 1, 0, 0, (0, 0));
    state.add_pack(first, false);
    state.add_pack(second, false);
    state.leave_pack(first_id, true, false);
    json!({"name": "multi_merge_leave_one", "state": state.to_value()})
}

fn case_group_merge_and_split() -> Value {
    let mut state = SourcePack::new();
    let arrows = state.make(WEAPON, 3, 10, 7, 0, (0, 0));
    let arrows_id = arrows.id;
    let same_group = state.make(WEAPON, 3, 5, 7, 0, (0, 0));
    let other_group = state.make(WEAPON, 3, 4, 8, 0, (0, 0));
    state.add_pack(arrows, false);
    state.add_pack(same_group, false);
    state.add_pack(other_group, false);
    state.leave_pack(arrows_id, true, false);
    json!({"name": "group_merge_split", "state": state.to_value()})
}

fn case_pack_overflow() -> Value {
    let mut state = SourcePack::new();
    for index in 0..MAXPACK {
        let obj = state.make(ARMOR, index as i32, 1, 0, 0, (0, 0));
        state.add_pack(obj, false);
    }
    let extra = state.make(ARMOR, 99, 1, 0, 0, (0, 0));
    let result = state.add_pack(extra.clone(), false);
    json!({"name": "pack_overflow", "result": result, "state": state.to_value(), "extra": extra})
}

fn case_scare_scroll_dust() -> Value {
    let mut state = SourcePack::new();
    let scroll = state.make(SCROLL, S_SCARE, 1, 0, ISFOUND, (3, 4));
    state.add_floor(scroll.clone());
    let result = state.add_pack(scroll, true);
    json!({"name": "scare_scroll_dust", "result": result, "state": state.to_value()})
}

fn case_leave_all_removes_packch() -> Value {
    let mut state = SourcePack::new();
    let food = state.make(FOOD, 0, 3, 0, 0, (0, 0));
    let food_id = food.id;
    state.add_pack(food, false);
    state.leave_pack(food_id, false, true);
    let replacement = state.make(POTION, 2, 1, 0, 0, (0, 0));
    state.add_pack(replacement, false);
    json!({"name": "leave_all_reuses_packch", "state": state.to_value()})
}

fn case_amulet_flag() -> Value {
    let mut state = SourcePack::new();
    let amulet = state.make(AMULET, 0, 1, 0, 0, (0, 0));
    state.add_pack(amulet, false);
    json!({"name": "amulet_flag", "state": state.to_value()})
}

fn is_mult(obj_type: &str) -> bool {
    obj_type == POTION.to_string() || obj_type == SCROLL.to_string() || obj_type == FOOD.to_string()
}
