"""Schemas function calling assistant v2: năm tool nghiệp vụ, update_trip và respond.

Schema nội bộ cho phép bỏ field tuỳ chọn; adapter OpenAI chuyển sang nullable strict. Mọi provider đều
được kiểm lại bằng jsonschema trước thực thi. Các cấu trúc draft/final giữ tương thích working memory v2.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

TAXONOMIES = ("hotel", "attraction", "combo", "golf", "flight")
MAX_CARDS_PER_TAXONOMY = 10


def _str(description: str, **kw) -> dict:
    return {"type": "string", "description": description, **kw}


def _int(description: str, low: int, high: int) -> dict:
    return {"type": "integer", "minimum": low, "maximum": high, "description": description}


def _bool(description: str) -> dict:
    return {"type": "boolean", "description": description}


def _list(items: dict, description: str, **kw) -> dict:
    return {"type": "array", "items": items, "description": description, **kw}


def _obj(description: str, **properties) -> dict:
    return {"type": "object", "description": description, "properties": properties,
            "required": list(properties), "additionalProperties": False}


def _opt(schema: dict) -> dict:
    """Cho phép null; null nghĩa là không dùng tham số đó (hoặc không đổi, với context_patch)."""
    nullable = {**schema, "type": [schema["type"], "null"]}
    if "enum" in schema:
        nullable["enum"] = [*schema["enum"], None]
    return nullable


REF = _str("Mã sản phẩm server cấp (p1, p2…), lấy từ products hoặc lịch sử; không tự đặt mã.", pattern="^p[0-9]+$")
CURSOR = _opt(_str("Con trỏ trang tiếp: chép nguyên coverage.next_cursor của lời gọi trước có cùng tham số."))
FREE_ONLY = _bool("true: chỉ giữ sản phẩm có căn cứ miễn phí (giá 0 hoặc không bán vé). Thiếu giá không phải miễn phí.")
EXCLUDE_REFS = _list(REF, "Mã loại khỏi kết quả, ví dụ thẻ đã giới thiệu khi khách muốn xem thêm. [] = không loại.")
TAXONOMY = _str("hotel khách sạn, attraction điểm tham quan/vui chơi, combo gói dịch vụ, golf sân golf, flight chuyến bay.",
                enum=list(TAXONOMIES))
DATE = _str("Ngày YYYY-MM-DD, giờ Việt Nam.", format="date")
DESTINATION = _str("Tên điểm đến đúng như danh sách điểm đến catalog, không phải cách khách viết (Sài Gòn, HCM…).")
PRICE = _int("VND cho một đơn vị giá của sản phẩm (đêm/người/gói), không phải ngân sách cả chuyến.", 0, 10**10)

SEARCH = _obj(
    "Tìm ngữ nghĩa trong catalog theo nhu cầu của khách. Kết quả xếp theo độ phù hợp; coverage cho biết còn trang.",
    query=_str("Điều khách muốn tìm (chủ đề, tiện ích, kiểu chỗ), bỏ từ đệm hội thoại.", minLength=1, maxLength=500),
    destination=_opt(_str("Tên điểm đến catalog. null = tìm toàn catalog; không tự lấy thành phố của thẻ cũ.")),
    taxonomy=_opt(TAXONOMY),
    price_min=_opt(PRICE),
    price_max=_opt(PRICE),
    star_rating_min=_opt(_int("Hạng sao tối thiểu của khách sạn.", 1, 5)),
    check_in=_opt(_str("Ngày nhận phòng/ngày dùng YYYY-MM-DD: chỉ giữ sản phẩm còn chỗ ngày đó.", format="date")),
    check_out=_opt(_str("Ngày trả phòng YYYY-MM-DD, sau check_in.", format="date")),
    guests=_opt(_int("Số khách MỘT phòng khi tìm khách sạn; đoàn đông dùng ceil(tổng khách / 9).", 1, 50)),
    limit=_opt(_int("Số ứng viên lấy về, null = 20. Không phải số thẻ sẽ giới thiệu.", 1, 50)),
    cursor=CURSOR, free_only=FREE_ONLY, exclude_refs=EXCLUDE_REFS)

RECOMMENDATIONS = _obj(
    "Gợi ý theo lịch sử của khách đang đăng nhập (server tự biết là ai) hoặc phổ biến khi chưa có lịch sử. "
    "data.strategy cho biết cá nhân hoá hay phổ biến; không nói là cá nhân hoá khi strategy là phổ biến.",
    k=_opt(_int("Số gợi ý, null = 5.", 1, 20)),
    destination=_opt(_str("Chỉ gợi ý ở điểm đến này; null = mọi nơi.")))

FLIGHTS = _obj(
    "Tra chuyến bay MỘT CHIỀU của một tuyến trong cả đợt mở bán. Trả các chuyến theo thứ tự yêu cầu và thống kê "
    "cả đợt (rẻ nhất, đắt nhất, ngày có/không có chuyến). Chiều về là một lời gọi khác, đảo nơi đi và nơi đến.",
    origin=_opt(_str("Thành phố khởi hành. null khi khách chưa nói: tool trả needs_input.")),
    destination=_opt(_str("Thành phố đến. null khi khách chưa nói: tool trả needs_input.")),
    date=_opt(_str("Chỉ trả chuyến của ngày này; thống kê cả đợt vẫn kèm theo.", format="date")),
    time_of_day=_opt(_str("early cất cánh trước 09:00, morning 05:00–12:00, afternoon 12:00–18:00, evening từ 18:00.",
                          enum=["early", "morning", "afternoon", "evening"])),
    sort=_opt(_str("price_asc giá tăng, price_desc giá giảm, departure_asc giờ bay sớm trước; null = price_asc.",
                   enum=["price_asc", "price_desc", "departure_asc"])),
    limit=_opt(_int("Số chuyến trả về, null = 5.", 1, 10)))

ACTIVITY = _obj(
    "Một hoạt động trong ngày.",
    product_ref=REF,
    start_minute=_int("Giờ bắt đầu: số phút từ 0 giờ, giờ Việt Nam (480 = 08:00).", 0, 1439),
    end_minute=_int("Giờ kết thúc, lớn hơn start_minute.", 1, 1440),
    timing_source=_str("catalog: thời lượng lấy từ durationMinutes của sản phẩm; estimate: bạn ước tính.",
                       enum=["catalog", "estimate"]),
    assumption=_opt(_str("Bắt buộc khi estimate: giả định về thời lượng, giờ mở cửa hay di chuyển.")))

BUILD = _obj(
    "Kiểm và tính tiền đúng lịch bạn phác: không tự thêm, bớt hay thay sản phẩm. Trả vi phạm phải sửa, cảnh báo phải "
    "nêu, tổng tiền và plan_result_id. Lịch có thể không có khách sạn (0 đêm) hay chuyến bay.",
    destination=DESTINATION, start_date=DATE,
    days=_int("Số ngày của chuyến.", 1, 7),
    adults=_int("Số người lớn.", 1, 50),
    children=_int("Số trẻ em.", 0, 50),
    origin=_opt(_str("Thành phố khởi hành khi lịch có chuyến bay.")),
    plan_days=_list(_obj("Một ngày của lịch.", day_index=_int("Ngày thứ mấy, từ 1.", 1, 7),
                         activities=_list(ACTIVITY, "Theo thứ tự trong ngày; nhiều hay ít tuỳ thời gian, có thể rỗng.")),
                    "Đủ mọi ngày từ 1 đến days.", minItems=1, maxItems=7),
    stays=_list(_obj("Một chặng lưu trú ở một hạng phòng.", product_ref=REF, check_in=DATE,
                     check_out=_str("Ngày trả phòng, sau check_in.", format="date")),
                "[] = không lưu trú."),
    flights=_list(_obj("Một chuyến bay đã chọn.", product_ref=REF,
                       role=_str("outbound chiều đi (ngày đầu), return chiều về (ngày cuối).",
                                 enum=["outbound", "return"])),
                  "[] = không bay."),
    trip_budget_vnd=_opt(_int("Ngân sách cả chuyến, VND. Vượt chỉ là cảnh báo.", 0, 10**11)),
    free_only=FREE_ONLY,
    locked_refs=_list(REF, "Sản phẩm khách đã chốt: giữ nguyên chỗ, tối ưu không di chuyển."),
    optimize=_str("none giữ nguyên thứ tự; reorder_within_day đổi thứ tự hoạt động trong ngày cho bớt đi lại "
                  "(chỉ khi đủ toạ độ và các hoạt động hoán đổi được).", enum=["none", "reorder_within_day"]))

CONTEXT_PATCH = _opt(_obj(
    "Thay đổi ngữ cảnh chuyến đi mà khách vừa nói rõ trong tin nhắn này (hoặc nút vừa bấm). Field null = không đổi.",
    destination=_opt(DESTINATION), start_date=_opt(DATE),
    days=_opt(_int("Số ngày.", 1, 7)), adults=_opt(_int("Số người lớn.", 1, 50)),
    children=_opt(_int("Số trẻ em.", 0, 50)), origin=_opt(_str("Thành phố khởi hành.")),
    trip_budget_vnd=_opt(_int("Ngân sách cả chuyến, VND.", 0, 10**11)),
    free_only=_opt(_bool("Khách chỉ muốn chỗ miễn phí.")),
    planning_consent=_opt(_bool("true khi khách đồng ý hoặc tự xin lập lịch.")),
    stopped=_opt(_bool("true khi ngừng lập lịch; false khi khách chủ động muốn tiếp tục. Không đồng nghĩa consent mới.")),
    engagement=_opt(_str("rekindle: mất hứng, khơi tò mò một lần bằng dữ liệu; stop: dừng rõ hoặc từ chối tiếp; "
                        "continue: khách chủ động tiếp tục khám phá. null = không đổi.",
                        enum=["rekindle", "stop", "continue"])),
    evidence=_str("Trích nguyên văn đoạn trong tin nhắn hiện tại, hoặc mã nút vừa bấm, làm căn cứ cho thay đổi.",
                  minLength=1)))

SEGMENT = {"anyOf": [
    _obj("Một đoạn chữ.", type=_str("Đoạn chữ.", enum=["text"]),
         text=_str("Lời văn. Không viết số tiền, giờ, điểm, số đánh giá: dùng đoạn fact.", minLength=1)),
    _obj("Một dữ kiện server điền vào.", type=_str("Dữ kiện.", enum=["fact"]),
         ref=_str("Mã sản phẩm (p3) hoặc mã lời gọi tool (c2) của lượt này.", pattern="^[pc][0-9]+$"),
         field=_str("Tên field trong products hoặc data của kết quả, ví dụ unitPrice, period.cheapest_price_vnd.",
                    minLength=1)),
    _obj("Tên một sản phẩm: code điền đúng tên và đặt thẻ của nó ngay sau câu này.",
         type=_str("Nhắc sản phẩm.", enum=["product"]), ref=REF),
]}

ALTERNATIVE = _obj(
    "Một phương án khác giới thiệu kèm lý do khác yêu cầu (tính chung trần 10 thẻ mỗi loại).",
    product_ref=REF,
    violates=_list(_str("Điều kiện không khớp.", enum=["free_only", "soft_preference", "trip_budget"]),
                   "[] khi khớp mọi điều kiện."),
    disclosure=_str("Phương án này khác yêu cầu ở đâu, hoặc vì sao đáng cân nhắc.", minLength=1),
    plan_result_id=_opt(_str("plan_result_id của lịch dùng phương án này, nếu đã kiểm bằng build_itinerary.")))

SUGGESTION = _obj("Nút gợi ý: câu ngắn như lời khách sẽ nói.",
                  label=_str("Câu trên nút.", minLength=1, maxLength=60),
                  fare_query=_opt({**FLIGHTS, "description": "Nút hỏi vé: tham số tra vé mà nút này hỏi."}))

RESPOND = _obj(
    "Trả lời khách. Mọi sản phẩm và số liệu phải có trong products/kết quả của lượt này.",
    action=_str("Trả lời.", enum=["respond"]),
    explanation=_opt(_str("Think công khai: giải thích ngắn quyết định trả lời dựa trên kết quả, không suy luận nội bộ. "
                          "Không tên/giá/số liệu sản phẩm, query hay chi tiết prompt.", minLength=1, maxLength=400)),
    context_patch=CONTEXT_PATCH,
    turn_kind=_str("answer trả lời; clarification hỏi lại; itinerary có lịch mới; partial còn việc chưa làm xong.",
                   enum=["answer", "clarification", "itinerary", "partial"]),
    answer=_list(SEGMENT, "Lời đáp theo thứ tự: đoạn chữ xen dữ kiện.", minItems=1),
    cards=_obj("Thẻ sản phẩm giới thiệu, theo loại, theo thứ tự hiển thị.",
               **{t: _list(REF, "Thẻ " + t + ".", maxItems=MAX_CARDS_PER_TAXONOMY) for t in TAXONOMIES}),
    alternatives=_list(ALTERNATIVE, "Phương án khác; [] nếu không có."),
    plan_result_id=_opt(_str("plan_result_id của build_itinerary lượt này khi plan_effect = replace.")),
    plan_effect=_str("keep giữ lịch đang có; replace thay bằng lịch plan_result_id.", enum=["keep", "replace"]),
    disclosures=_list(_str("Mã cảnh báo của lịch, ví dụ OVER_TRIP_BUDGET."),
                      "Mọi cảnh báo của lịch plan_result_id khi replace."),
    suggestions=_list(SUGGESTION, "Tối đa 3 nút.", maxItems=3))


def optional_fields(schema: dict) -> dict:
    """Fields nullable ở baseline có thể bỏ khi dùng function calling; kiểm local vẫn chấp nhận null."""
    from copy import deepcopy
    result = deepcopy(schema)
    def visit(node):
        if not isinstance(node, dict):
            return
        if "properties" in node:
            node["required"] = [key for key, value in node["properties"].items()
                                if "null" not in (value.get("type") if isinstance(value.get("type"), list) else [])]
        for value in node.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
    visit(result)
    return result


def _parameters(description: str, required: list[str], **properties) -> dict:
    return {"type": "object", "description": description, "properties": properties,
            "required": required, "additionalProperties": False}


WHY = _str("Một câu ghi chú công việc công khai: vì sao cần gọi tool, không tên/giá/số liệu.", minLength=1, maxLength=400)
FIND = _parameters(
    "Tìm catalog: có query thì Search theo độ khớp; bỏ query thì duyệt theo sort. Khách sạn trả kèm hạng phòng. "
    "Mỗi khách sạn kèm phòng tốn thêm một request nguồn; coverage.rooms cho biết phần chưa đọc được.",
    ["why", "taxonomy"], why=WHY, taxonomy={**TAXONOMY, "enum": ["hotel", "attraction", "combo", "golf"]},
    destination=_opt(_str("Phạm vi tìm của lượt này, không phải điểm đến lịch đã lưu. null = mọi nơi. "
                         "Khách nói ngoài Phan Thiết: null và excluded_destinations=[Phan Thiết].")),
    query=_opt(SEARCH["properties"]["query"]),
    name_contains=_opt(_str("Cụm tên riêng phải có nguyên cụm trong tên kết quả, bỏ qua dấu/hoa thường. "
                           "Ví dụ Le Phan: nhận Khách sạn Lê Phan, không nhận Le Aqua. Không dùng cho chủ đề.",
                           minLength=1, maxLength=200)),
    excluded_destinations=_opt(_list(DESTINATION, "Các điểm đến khách loại trong lần tìm này; không đổi lịch. "
                                   "Không đồng nghĩa ngoài trời.", maxItems=20)),
    sort=_opt(_str("Có query: relevance giữ thứ tự Search; price_asc/desc chỉ sắp trang đã tìm, không cả catalog. "
                  "Không query: popular/price_asc/price_desc theo Catalog.",
                  enum=["relevance", "popular", "price_asc", "price_desc"])),
    price_max=_opt(PRICE), star_rating_min=SEARCH["properties"]["star_rating_min"],
    check_in=SEARCH["properties"]["check_in"], check_out=SEARCH["properties"]["check_out"],
    free_only=_opt(FREE_ONLY), exclude_refs=_opt(EXCLUDE_REFS),
    limit=_opt(_int("Số ứng viên; mặc định 10. Không phải số thẻ hiển thị.", 1, 20)), cursor=CURSOR,
    parent_ref=_opt(_str("Mã khách sạn để lấy trang hạng phòng khi phần rooms chưa đủ.", pattern="^p[0-9]+$")))
GET = _parameters("Đọc mới tối đa mười sản phẩm, kèm hạng phòng khi include_rooms. Một request nguồn mỗi ref; "
                  "kèm phòng tốn thêm một request mỗi khách sạn. Lỗi từng ref không huỷ refs khác.",
                  ["why", "refs"], why=WHY, refs=_list(REF, "Refs cần refresh.", minItems=1, maxItems=10),
                  include_rooms=_opt(_bool("Kèm phòng đặt được của khách sạn.")))
RECOMMEND = _parameters("Gợi ý theo khách/phổ biến; like_ref thì lấy Similar cùng loại. strategy cho biết căn cứ.",
    ["why"], why=WHY, destination=_opt(DESTINATION), taxonomy=_opt(TAXONOMY), like_ref=_opt(REF),
    k=RECOMMENDATIONS["properties"]["k"], exclude_refs=_opt(EXCLUDE_REFS))
PLAN = _parameters("Orc chọn sản phẩm từng buổi. Code tính giờ, đêm (= ngày − 1), phòng, tiền; không đổi sản phẩm. "
                   "Combo gợi ý riêng ở cards.combo. Lỗi có fix_hint để bạn sửa buổi; không trả lịch infeasible.",
    ["why", "destination", "start_date", "days", "adults", "schedule"],
    why=WHY, destination=DESTINATION, start_date=DATE, days=BUILD["properties"]["days"],
    adults=BUILD["properties"]["adults"], children=_opt(BUILD["properties"]["children"]),
    budget_vnd=BUILD["properties"]["trip_budget_vnd"], origin=BUILD["properties"]["origin"],
    free_only=_opt(FREE_ONLY), locked_refs=_opt(EXCLUDE_REFS),
    schedule=_list(_parameters("Một ngày đủ buổi khách cần; cùng ref morning/afternoon = hoạt động cả ngày.",
                   ["day"], day=_int("Ngày từ một.", 1, 7), morning=_opt(REF), afternoon=_opt(REF), evening=_opt(REF)),
                   "Đủ mọi ngày; ngày trọn vẹn hai hoặc ba hoạt động nếu catalog có đủ.", minItems=1, maxItems=7),
    stays=_opt(_list(_parameters("Một chặng phòng; mặc định nhận ngày đầu, trả ngày cuối.", ["room_ref"],
                  room_ref=REF, from_day=_opt(_int("Ngày nhận phòng.", 1, 7)),
                  to_day=_opt(_int("Ngày trả phòng.", 1, 7)), rooms=_opt(_int("Chỉ khi khách nói rõ số phòng.", 1, 9))),
                  "Bỏ trống = không lưu trú.")),
    flights=_opt(_parameters("Chọn chuyến tới đúng nơi và ngày; chiều về đảo tuyến.", [],
                             outbound=_opt(REF), **{"return": _opt(REF)})),
    fixed_times=_opt(_list(_parameters("Giữ giờ cố định khách yêu cầu; phải nằm trong buổi.",
                       ["day", "slot", "start_minute"], day=_int("Ngày.", 1, 7),
                       slot=_str("Buổi.", enum=["morning", "afternoon", "evening"]),
                       start_minute=_int("Phút từ nửa đêm.", 0, 1439)), "Các mốc giờ phải giữ.")))
UPDATE_TRIP = optional_fields(CONTEXT_PATCH)
UPDATE_TRIP["type"] = "object"
UPDATE_TRIP["required"] = ["evidence"]
# budget_vnd là tên tool; working memory giữ trip_budget_vnd để tương thích hội thoại đã lưu.
UPDATE_TRIP["properties"]["budget_vnd"] = UPDATE_TRIP["properties"].pop("trip_budget_vnd")
FINAL = optional_fields(RESPOND)
FINAL["properties"].pop("action")
FINAL["required"].remove("action")
# Clarification can save the new trip fields atomically with its answer, including in the final-only round.
# Same evidence/schema checks and commit boundary as update_trip; omitted/null fields preserve prior context.
FLIGHT_PARAMETERS = optional_fields(FLIGHTS)
FLIGHT_PARAMETERS["properties"]["why"] = WHY
FLIGHT_PARAMETERS["required"].append("why")
TOOLS = {"find_products": FIND, "get_products": GET, "recommend": RECOMMEND,
         "lookup_flights": FLIGHT_PARAMETERS, "plan_itinerary": PLAN}
CONTROL_TOOLS = {"update_trip": UPDATE_TRIP, "respond": FINAL}


def function_tools(allowed: list[str], can_execute: bool = True) -> list[dict]:
    names = [*allowed, "update_trip", "respond"] if can_execute else ["respond"]
    return [{"type": "function", "function": {"name": name, "description": schema["description"],
             "parameters": schema}} for name in names for schema in [TOOLS.get(name) or CONTROL_TOOLS[name]]]


def tool_errors(name: str, arguments: Any) -> list[str]:
    schema = TOOLS.get(name) or CONTROL_TOOLS.get(name)
    if schema is None:
        return ["tool: TOOL_NOT_ALLOWED"]
    return decision_errors(arguments, schema)


def decision_errors(value: Any, schema: dict) -> list[str]:
    errors = []
    for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value):
        while error.context:
            error = max(error.context, key=lambda item: len(item.absolute_path))
        path = "/".join(str(part) for part in error.absolute_path) or "arguments"
        errors.append(f"{path}: {error.message[:200]}")
    return errors
