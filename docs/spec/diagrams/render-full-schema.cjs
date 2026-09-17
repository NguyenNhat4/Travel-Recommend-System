/* Render one complete ERD. Requires @viz-js/viz; set SCHEMA_NODE_MODULES if needed.
   This is a documentation renderer, not a database migration. */
const fs=require('fs');
const path=require('path');
const moduleRoot=process.env.SCHEMA_NODE_MODULES;
const {instance}=moduleRoot?require(path.join(moduleRoot,'@viz-js/viz/dist/viz.cjs')):require('@viz-js/viz');
const here=__dirname;
const tables=[];
const relations=[];
const C=[['product_id','uuid','PK FK'],['product_kind','varchar(24)','FK CHECK'],['name','text','NN'],['destination','text','NN'],['description','text','NULL'],['image_url','text','NULL'],['attributes','jsonb','NN']];
const SNAP=[['unit_price','bigint','NULL'],['currency','varchar(3)','VND'],['price_unit','varchar','UNKNOWN'],['source_available','boolean','NN'],['source_available_from','date','NULL'],['source_available_to','date','NULL']];
function t(db,group,name,fields,note='',optional=false){tables.push({db,group,name,fields,note,optional});}
function f(s){return s.split(';').map(x=>x.split('|'));}
function cat(name,kind,group,extra,note,room=false){t('ota_app',group,name,[...C,...f(extra),...(room?[]:SNAP)],`CHECK product_kind = ${kind}. ${note}`);}
function r(db,parent,child,pc,cc,card='1 → 0..N',label=''){relations.push({from:`${db}.${parent}`,to:`${db}.${child}`,parentColumns:pc.split(','),childColumns:cc.split(','),card,label:label||cc,fk:true});}
function soft(from,to,pc,cc,label){relations.push({from,to,parentColumns:pc.split(','),childColumns:cc.split(','),card:'ID reference',label,fk:false});}

t('ota_app','catalog','catalog_keys',f('product_id|uuid|PK;product_kind|varchar(24)|NN UK¹;source_ref|text|UK;created_at|timestamptz|NN;updated_at|timestamptz|NN;deleted_at|timestamptz|NULL'),'UK¹ (product_id, product_kind). Chính xác 1 subtype / ID; không lưu nội dung sản phẩm.');
cat('hotel_properties','HOTEL_PROPERTY','catalog','address|text|NULL;property_type|text|NULL;star_rating|numeric|NULL;latitude|numeric|NULL;longitude|numeric|NULL;amenities|text[]|NN','1.494 cơ sở; không đặt trực tiếp. Giá card từ room con.');
cat('hotel_rooms','HOTEL_ROOM','catalog','property_product_id|uuid|FK NN;room_name|text|NN;room_code|text|NULL;room_size_m2|numeric|NULL;max_occupancy|int|NULL;max_adult|int|NULL;max_child|int|NULL;bedrooms|int|NULL;bed_description|text|NULL;amenities|text[]|NN','4.646 hạng phòng; mỗi hạng = 1 đơn vị tồn mock / đêm.',true);
cat('flight_routes','FLIGHT_ROUTE','catalog','origin_city|text|NN;destination_city|text|NN;origin_destination|text|NN;origin_airports|text[]|NN;destination_airports|text[]|NN;airlines|text[]|NN;round_trip_from|bigint|NULL;monthly_prices|jsonb|NULL','60 tuyến; không phải vé có ngày bay cụ thể.');
cat('flight_services','FLIGHT_SERVICE','catalog','route_product_id|uuid|FK NN;flight_number|text|NN;airline|text|NN;airline_code|text|NN;origin_airport|text|NN;destination_airport|text|NN;departure_time_local|time|NN;arrival_time_local|time|NN;duration_minutes|int|NULL;nonstop|boolean|NN;price_observed_on|date|NN','184 chuyến; ngày quan sát không là tồn ghế.');
cat('attraction_products','ATTRACTION','catalog','attraction_kind|varchar|TICKET/TOUR/POI/UNKNOWN;ticketed|boolean|NULL;venue|text|NULL;tour_code|text|NULL;supplier|text|NULL;duration_minutes|int|NULL;opening_hours|text|NULL;departure|text|NULL;child_price|bigint|NULL;member_prices|jsonb|NULL;policies|jsonb|NULL','3.517 vé / tour / điểm tham quan; ticketed=false không được đặt.');
cat('combo_packages','COMBO','catalog','tour_code|text|NULL;venue|text|NULL;supplier|text|NULL;composition_status|varchar|UNMAPPED/PARTIAL/VERIFIED;child_price|bigint|NULL;member_prices|jsonb|NULL;policies|jsonb|NULL','93 gói; không mặc định có phòng; không cộng quyền lợi hai lần.');
cat('golf_products','GOLF','catalog','golf_kind|varchar|VOUCHER/VENUE/UNKNOWN;ticketed|boolean|NULL;venue|text|NULL;tour_code|text|NULL;length_of_tour_raw|text|NULL;opening_hours|text|NULL;policies|jsonb|NULL','6 voucher / địa điểm golf; điều kiện tee time trong policies.');
t('ota_app','inventory','hotel_room_prices',f('room_product_id|uuid|PK FK;nightly_price|bigint|NN CHECK >= 0;currency|varchar(3)|VND;price_unit|varchar|PER_NIGHT;pricing_mode|varchar|MOCK_FIXED;price_version|bigint|NN;priced_at|timestamptz|NN'),'1 giá / room. Qua ngày mới không đổi giá.');
t('ota_app','inventory','hotel_room_nights',f('room_product_id|uuid|PK FK¹ FK²;stay_date|date|PK;available|boolean|NN;booking_item_id|uuid|FK² NULL;updated_at|timestamptz|NN'),'PK (room, date). 30 đêm active. Có booking ⇒ available=false.');
t('ota_app','catalog','flight_observed_dates',f('flight_product_id|uuid|PK FK;departure_date|date|PK'),'Từ attributes.datesSeen; không suy liên tục từ min–max.');
t('ota_app','catalog','combo_components',f('combo_product_id|uuid|PK FK;component_no|int|PK;component_product_id|uuid|FK NULL;benefit_label|text|NN;included_quantity|numeric|NULL;unit|text|NULL;source_evidence|text|NN'),'Mapping quyền lợi có chứng cứ; có thể rỗng khi chưa mapping.');
t('ota_app','identity','users',f('user_id|uuid|PK;email|text|UK NN;password_hash|text|NN;full_name|text|NN;cdp_user_id|varchar(64)|UK NN;created_at|timestamptz|NN'),'Tài khoản mẫu seed trực tiếp. Không có demo_accounts.');
t('ota_app','identity','carts',f('cart_id|uuid|PK;user_id|uuid|FK UK;version|bigint|NN;updated_at|timestamptz|NN'),'Một giỏ / user; giỏ không giữ chỗ.');
t('ota_app','identity','cart_items',f('cart_item_id|uuid|PK;cart_id|uuid|FK;product_id|uuid|FK¹;product_kind|varchar(24)|FK¹;using_date|date|NN;nights|int|NULL ngoài phòng;quantity|int|NN;unit_price_at_add|bigint|NN;price_version_at_add|bigint|NULL ngoài phòng;updated_at|timestamptz|NN'),'Phòng: quantity=1, nights>=1; partial UK (cart_id, product_id).');
t('ota_app','booking','bookings',f('booking_id|uuid|PK;user_id|uuid|FK;reference_code|varchar(18)|UK;status|varchar|CONFIRMED;contact_full_name|text|NN;contact_email|text|NN;contact_phone|text|NN;total|bigint|NN;currency|varchar(3)|VND;created_at|timestamptz|NN'),'Giá trị đơn chốt; user/catalog liên quan không cascade delete.');
t('ota_app','booking','booking_groups',f('booking_group_id|uuid|PK;booking_id|uuid|FK;destination|text|NN;event_group_id|varchar(64)|UK;group_total|bigint|NN'),'UK (booking_id, destination).');
t('ota_app','booking','booking_items',f('booking_item_id|uuid|PK;booking_group_id|uuid|FK;product_id|uuid|FK¹;product_kind|varchar(24)|FK¹;using_date|date|NN;nights|int|NULL ngoài phòng;quantity|int|NN;unit_price|bigint|NN;price_unit|varchar|NN;line_total|bigint|NN;product_snapshot|jsonb|NN;guest_names|text[]|NN;special_request|text|NULL'),'Snapshot tên, loại, điểm đến, ảnh; tiền không đọc lại từ catalog sống.');
t('ota_app','booking','booking_room_stays',f('booking_item_id|uuid|PK FK;room_product_id|uuid|FK;check_in|date|NN;check_out|date|NN'),'UK (booking_item_id, room_product_id). checkOut > checkIn; khớp item.');
t('ota_app','booking','checkout_requests',f('checkout_id|uuid|PK;user_id|uuid|FK;idempotency_key|text|NN;request_hash|text|NN;cart_snapshot|jsonb|NN;state|varchar|NN;booking_id|uuid|FK NULL;response_snapshot|jsonb|NULL;created_at|timestamptz|NN;updated_at|timestamptz|NN'),'UK (user_id, key). PROCESSING / SUCCEEDED / FAILED / RECONCILING.');
t('ota_app','booking','checkout_purchase_journal',f('checkout_id|uuid|PK FK;event_id|varchar(128)|PK;planned_booking_item_id|uuid|NN không FK;cdp_user_id|varchar(64)|NN;event_payload|jsonb|NN;state|varchar|NN;updated_at|timestamptz|NN'),'PREPARED / ACKED / CANCEL_PENDING / CANCELLED; đối soát sau lỗi.');
t('ota_app','search','product_vectors',f('product_id|uuid|PK FK;model|text|PK;text_version|text|PK;dim|int|NN;embedding|vector|NN;embedded_at|timestamptz|NN'),'Chốt vector(N) theo model. Không tạo database vector thứ tư.');
t('ota_app','search','product_popularity',f('product_id|uuid|PK FK;purchase_count|bigint|NN;window_days|int|NN;data_source|text|NN;computed_at|timestamptz|NN'),'Snapshot seed/job; không join trực tiếp DB CDP.');
t('ota_app','search','assistant_conversations',f('conversation_id|varchar(64)|PK;user_id|uuid|FK NULL;anonymous_session_hash|text|NULL;intent|jsonb|NN;updated_at|timestamptz|NN;expires_at|timestamptz|NN'),'Đề xuất nếu lưu Postgres; kiểm ownership và hết hạn 24h.',true);
t('cdp','customer','profiles',f('cdp_user_id|varchar(64)|PK;lifecycle_stage|varchar(16)|NULL;days_since_last_booking|int|NULL;lifetime_order_count|int|NULL;vinclub_tier|varchar(32)|NULL;purchased_verticals|jsonb|NN;home_city|text|NULL;last_destination|text|NULL;email_optin|boolean|NULL;sms_optin|boolean|NULL;push_optin|boolean|NULL;gdpr_optin|boolean|NULL;updated_at|timestamptz|NN'),'Snapshot do seed/job ghi qua API; null không tự là opt-in.');
t('cdp','customer','events',f('id|bigint|PK;cdp_user_id|varchar(64)|NN UK¹;event_id|varchar(128)|NN UK¹;event_name|varchar(32)|NN;timestamp|timestamptz|NN;product_id|varchar(128)|NULL không FK;taxonomy|varchar(16)|NULL;event_group_id|varchar(64)|NULL;quantity|int|NULL;unit_price|bigint|NULL đề xuất;using_date|date|NULL;search_query|varchar(500)|NULL;received_at|timestamptz|NN;cancelled_at|timestamptz|NULL'),'UK¹ (cdp_user_id, event_id). Giữ vĩnh viễn. Code tham chiếu dùng Float cho tiền.');
t('insider','activation','insider_profiles',f('insider_id|uuid|PK;attributes|jsonb|NN;created_at|timestamptz|NN;updated_at|timestamptz|NN'),'Bản sao profile/consent + custom chứa top gợi ý.');
t('insider','activation','identifiers',f('id|bigint|PK;insider_id|uuid|FK;identifier_type|text|NN;identifier_value|text|NN;updated_at|timestamptz|NN'),'UK (type,value); UK (insider_id,type). Đề xuất uuid = cdpUserId.');
t('insider','activation','insider_events',f('id|bigint|PK;insider_id|uuid|FK;event_name|text|NN;timestamp|timestamptz|NN;event_group_id|text|NULL;event_params|jsonb|NN;received_at|timestamptz|NN;expires_at|timestamptz|NN'),'TTL 90 ngày; purchase 730 ngày, theo handbook clone.');
t('insider','activation','channel_events',f('id|bigint|PK;insider_id|uuid|FK;channel|text|NN;event_name|text|NN;campaign_id|text|NULL;timestamp|timestamptz|NN;params|jsonb|NN'),'Tương tác email / push / SMS của clone.');
t('insider','activation','identifier_changes',f('id|bigint|PK;insider_id|uuid|FK;identifier_type|text|NN;old_value|text|NN;new_value|text|NN;changed_at|timestamptz|NN'),'Nhật ký đổi identifier; tùy chọn.',true);

for(const name of ['hotel_properties','hotel_rooms','flight_routes','flight_services','attraction_products','combo_packages','golf_products'])r('ota_app','catalog_keys',name,'product_id,product_kind','product_id,product_kind','1 → 0..1','ID + kind; XOR 7 subtype');
r('ota_app','hotel_properties','hotel_rooms','product_id','property_product_id');
r('ota_app','hotel_rooms','hotel_room_prices','product_id','room_product_id','1 → 1');
r('ota_app','hotel_rooms','hotel_room_nights','product_id','room_product_id','1 → 0..N','FK¹ room; 30 đêm active');
r('ota_app','flight_routes','flight_services','product_id','route_product_id');
r('ota_app','flight_services','flight_observed_dates','product_id','flight_product_id');
r('ota_app','combo_packages','combo_components','product_id','combo_product_id');
r('ota_app','catalog_keys','combo_components','product_id','component_product_id','0..1 → 0..N');
r('ota_app','users','carts','user_id','user_id','1 → 0..1');
r('ota_app','carts','cart_items','cart_id','cart_id');
r('ota_app','catalog_keys','cart_items','product_id,product_kind','product_id,product_kind');
r('ota_app','users','bookings','user_id','user_id');
r('ota_app','bookings','booking_groups','booking_id','booking_id','1 → 1..N');
r('ota_app','booking_groups','booking_items','booking_group_id','booking_group_id','1 → 1..N');
r('ota_app','catalog_keys','booking_items','product_id,product_kind','product_id,product_kind');
r('ota_app','booking_items','booking_room_stays','booking_item_id','booking_item_id','1 → 0..1');
r('ota_app','hotel_rooms','booking_room_stays','product_id','room_product_id');
r('ota_app','booking_room_stays','hotel_room_nights','booking_item_id,room_product_id','booking_item_id,room_product_id','0..1 → 1..N','FK² booking item + room');
r('ota_app','users','checkout_requests','user_id','user_id');
r('ota_app','bookings','checkout_requests','booking_id','booking_id','0..1 → 0..N');
r('ota_app','checkout_requests','checkout_purchase_journal','checkout_id','checkout_id');
r('ota_app','catalog_keys','product_vectors','product_id','product_id');
r('ota_app','catalog_keys','product_popularity','product_id','product_id','1 → 0..1');
r('ota_app','users','assistant_conversations','user_id','user_id','0..1 → 0..N');
for(const name of ['identifiers','insider_events','channel_events','identifier_changes'])r('insider','insider_profiles',name,'insider_id','insider_id',name==='identifiers'?'1 → 1..N':'1 → 0..N');
soft('ota_app.users','cdp.profiles','cdp_user_id','cdp_user_id','cdpUserId qua API; không FK');
soft('ota_app.users','cdp.events','cdp_user_id','cdp_user_id','cdpUserId; user có thể chưa có profile');
soft('cdp.profiles','cdp.events','cdp_user_id','cdp_user_id','cùng ID trong CDP; không FK');
soft('ota_app.catalog_keys','cdp.events','product_id','product_id','productId cụ thể; không FK');
soft('ota_app.booking_groups','cdp.events','event_group_id','event_group_id','eventGroupId; không FK');
soft('ota_app.checkout_purchase_journal','cdp.events','cdp_user_id,event_id','cdp_user_id,event_id','purchase:{bookingItemId}; idempotency');
soft('cdp.profiles','insider.identifiers','cdp_user_id','identifier_value','đề xuất identifier_type=uuid; không FK');

const byName=new Map(tables.map(x=>[x.db+'.'+x.name,x]));
if(tables.length!==31||new Set(tables.map(x=>x.db)).size!==3)throw Error('Unexpected table/db count');
for(const table of tables){if(new Set(table.fields.map(x=>x[0])).size!==table.fields.length)throw Error('Duplicate column '+table.name);}
for(const rel of relations){for(const [table,cols] of [[rel.from,rel.parentColumns],[rel.to,rel.childColumns]]){const t=byName.get(table);if(!t)throw Error('Unknown table '+table);for(const c of cols)if(!t.fields.some(f=>f[0]===c))throw Error('Unknown column '+table+'.'+c);}if(rel.fk&&rel.from.split('.')[0]!==rel.to.split('.')[0])throw Error('Cross-database FK');}
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const q=s=>JSON.stringify(s);
const id=s=>s.replace('.','__');
function wrap(s,n=52){let lines=[''];for(const word of s.split(' ')){if((lines.at(-1)+' '+word).length>n)lines.push(word);else lines[lines.length-1]+=(lines.at(-1)?' ':'')+word;}return lines;}
const palettes={ota_app:['#1d4ed8','#dbeafe','#f8fbff'],cdp:['#c2410c','#ffedd5','#fffbf5'],insider:['#6d28d9','#ede9fe','#fcfaff']};
let dot='digraph FullSchema {\ngraph [rankdir=TB,bgcolor="white",fontname="DejaVu Sans",pad=0.5,nodesep=0.55,ranksep=1.1,splines=polyline,compound=true,newrank=true];\nnode [fontname="DejaVu Sans",fontsize=12,shape=plain];\nedge [fontname="DejaVu Sans",fontsize=10,color="#64748b",arrowsize=0.7];\n';
const titles={ota_app:'DB 1: ota_app — 24 bảng · sản phẩm, lịch phòng, tài khoản, đặt chỗ, vector',cdp:'DB 2: cdp — 2 bảng · hồ sơ và lịch sử hành vi',insider:'DB 3: insider — 5 bảng · bản sao kích hoạt kênh'};
for(const db of ['ota_app','cdp','insider']){const [border,header,bg]=palettes[db];dot+=`subgraph cluster_${db} { label=${q(titles[db])}; labelloc=t; labeljust=l; fontsize=24; fontcolor=${q(border)}; color=${q(border)}; penwidth=3; style="rounded,filled"; fillcolor=${q(bg)}; margin=28;\n`;
 for(const table of tables.filter(x=>x.db===db)){const rows=table.fields.map(([name,type,flags])=>`<TR><TD ALIGN="LEFT" PORT="${name}">${escape(name)}</TD><TD ALIGN="LEFT">${escape(type)}</TD><TD ALIGN="LEFT"><FONT COLOR="#475569">${escape(flags||'')}</FONT></TD></TR>`).join('');const notes=wrap(table.note).map(x=>`<TR><TD ALIGN="LEFT" COLSPAN="3"><FONT POINT-SIZE="10" COLOR="#475569">${escape(x)}</FONT></TD></TR>`).join('');dot+=`${id(db+'.'+table.name)} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white" COLOR="${border}"><TR><TD COLSPAN="3" BGCOLOR="${table.optional?'#f1f5f9':header}"><B>${escape(table.name)}${table.optional?' [tùy chọn]':''}</B></TD></TR><TR><TD ALIGN="LEFT"><B>Cột</B></TD><TD ALIGN="LEFT"><B>Kiểu</B></TD><TD ALIGN="LEFT"><B>Khóa / null</B></TD></TR>${rows}${notes}</TABLE>>];\n`;}
 dot+='}\n';}
for(const rel of relations){const head=rel.card.split(' → ');dot+=`${id(rel.from)} -> ${id(rel.to)} [label=${q(rel.label)},taillabel=${q(rel.fk?head[0]:'')},headlabel=${q(rel.fk?head[1]:'')},dir=both,arrowhead=none,arrowtail=none,style=${rel.fk?'solid':'dashed'},color=${q(rel.fk?'#64748b':'#a8550b')},${rel.fk?'':'constraint=false,'}penwidth=${rel.fk?'1':'1.4'}];\n`;}
dot+='}\n';
(async()=>{const viz=await instance();const out=viz.render(dot,{format:'svg',engine:'dot'});if(out.status!=='success')throw Error(JSON.stringify(out.errors));let svg=out.output.replace('<svg ','<svg role="img" aria-labelledby="full-schema-title" ');svg=svg.replace(/<title>[^<]*<\/title>/,'<title id="full-schema-title">Toàn bộ schema 3 database: 31 bảng, khóa chính, khóa ngoại và tham chiếu ID</title>');fs.writeFileSync(path.join(here,'schema-database-toan-bo.svg'),svg);fs.writeFileSync(path.join(here,'schema-database-toan-bo.dot'),dot);fs.writeFileSync(path.join(here,'schema-database-toan-bo.json'),JSON.stringify({status:'proposed-not-migrated',date:'2026-09-17',tables,relations},null,2)+'\n');console.log(JSON.stringify({databases:3,tables:tables.length,foreignKeys:relations.filter(x=>x.fk).length,idReferences:relations.filter(x=>!x.fk).length,warnings:out.errors,svgBytes:svg.length}));})().catch(e=>{console.error(String(e));process.exitCode=1});
