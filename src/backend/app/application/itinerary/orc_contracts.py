"""Schema quyết định của orc trong assistant v2: tham số tám tool và hai dạng quyết định execute/respond.

Schema viết sẵn ở dạng OpenAI strict mode nhận được: mọi field đều bắt buộc (không dùng thì null), không có
`uniqueItems`/`default`. Cùng một schema vừa gửi cho model vừa dùng để kiểm quyết định model trả về, nên provider
không ép schema (Gemini, Anthropic) cũng được kiểm như nhau. Bounds khớp OpenAPI nguồn (test kiểm).
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
DESTINATION = _str("Tên điểm đến đúng như catalog (list_destinations).")
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

SIMILAR = _obj("Sản phẩm cùng loại tương tự một sản phẩm đã biết, khi khách muốn đổi món.",
               product_ref=REF, limit=_opt(_int("Số kết quả, null = 8.", 1, 20)))

DETAIL = _obj("Đọc dữ kiện mới nhất của một sản phẩm đã biết (giá, giờ mở cửa, tiện ích, địa chỉ, mô tả đầy đủ). "
              "Bắt buộc trước khi nói lại dữ kiện hay hiện lại thẻ của sản phẩm chỉ có trong lịch sử.", product_ref=REF)

DESTINATIONS = _obj("Danh sách điểm đến hệ thống có dữ liệu. Không gọi khi khách đã nêu một nơi cụ thể: dùng thẳng "
                    "tên đó với list_products/search_products (rỗng nghĩa là nơi đó chưa có dữ liệu).")

LIST_PRODUCTS = _obj(
    "Duyệt catalog có cấu trúc, không hiểu câu chữ: theo điểm đến, loại, sản phẩm cha, sắp theo giá. "
    "Dùng cho rẻ nhất/đắt nhất cả điểm đến hoặc liệt kê hạng phòng của một khách sạn.",
    destination=_opt(DESTINATION), taxonomy=_opt(TAXONOMY),
    parent_ref=_opt(_str("Mã khách sạn để liệt kê hạng phòng (sản phẩm đặt được).", pattern="^p[0-9]+$")),
    sort=_opt(_str("popular phổ biến, price_asc giá tăng, price_desc giá giảm; null = popular.",
                   enum=["popular", "price_asc", "price_desc"])),
    available_only=_bool("true: chỉ sản phẩm đang bán."),
    limit=_opt(_int("Số kết quả, null = 20.", 1, 50)),
    cursor=CURSOR, free_only=FREE_ONLY, exclude_refs=EXCLUDE_REFS)

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

TOOLS: dict[str, dict] = {
    "search_products": SEARCH, "get_recommendations": RECOMMENDATIONS, "get_similar_products": SIMILAR,
    "get_product_detail": DETAIL, "list_destinations": DESTINATIONS, "list_products": LIST_PRODUCTS,
    "lookup_flights": FLIGHTS, "build_itinerary": BUILD,
}

CONTEXT_PATCH = _opt(_obj(
    "Thay đổi ngữ cảnh chuyến đi mà khách vừa nói rõ trong tin nhắn này (hoặc nút vừa bấm). Field null = không đổi.",
    destination=_opt(DESTINATION), start_date=_opt(DATE),
    days=_opt(_int("Số ngày.", 1, 7)), adults=_opt(_int("Số người lớn.", 1, 50)),
    children=_opt(_int("Số trẻ em.", 0, 50)), origin=_opt(_str("Thành phố khởi hành.")),
    trip_budget_vnd=_opt(_int("Ngân sách cả chuyến, VND.", 0, 10**11)),
    free_only=_opt(_bool("Khách chỉ muốn chỗ miễn phí.")),
    planning_consent=_opt(_bool("true khi khách đồng ý hoặc tự xin lập lịch.")),
    stopped=_opt(_bool("true khi khách không muốn đi/lập lịch nữa; false khi khách muốn tiếp tục.")),
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


def _call(name: str) -> dict:
    """Mã lời gọi (c1, c2…) do server đánh theo thứ tự trong lượt, model không phải tự đặt."""
    return _obj("Gọi " + name + ".", name=_str("Tên tool.", enum=[name]), arguments=TOOLS[name])


def decision_schema(tools: list[str], can_execute: bool = True) -> dict:
    """Schema của một quyết định. Hết lượt gọi tool hoặc hết giờ thì chỉ còn dạng respond."""
    choices = [RESPOND]
    if can_execute and tools:
        execute = _obj("Gọi 1–3 tool độc lập; mọi kết quả quay lại cho bạn.",
                       action=_str("Gọi tool.", enum=["execute"]), context_patch=CONTEXT_PATCH,
                       calls=_list({"anyOf": [_call(name) for name in tools]}, "Các lời gọi độc lập.",
                                   minItems=1, maxItems=3))
        choices.insert(0, execute)
    schema = _obj("Một quyết định của orc.", decision={"anyOf": choices})
    schema["title"] = "OrcDecision"
    return schema


def decision_errors(value: Any, schema: dict) -> list[str]:
    """Lỗi schema của quyết định model trả về, dạng `đường/dẫn: lý do` để orc tự sửa.

    Với anyOf, lấy lỗi sâu nhất: đó là nhánh model định dùng (ví dụ đúng tên tool nhưng sai một tham số).
    """
    errors = []
    for error in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value):
        while error.context:
            error = max(error.context, key=lambda item: len(item.absolute_path))
        path = "/".join(str(part) for part in error.absolute_path) or "decision"
        errors.append(f"{path}: {error.message[:200]}")
    return errors
