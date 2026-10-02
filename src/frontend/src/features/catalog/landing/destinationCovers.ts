/**
 * Ảnh bìa theo nhãn điểm đến. `GET /destinations` chỉ trả tên và số sản phẩm, không có ảnh, nên ảnh là bản đồ tĩnh
 * theo nhãn chuẩn hóa; nhãn chưa có trong bản đồ thì dùng nền gradient (DestinationTiles).
 */
const cover = (photo: string) => `https://images.unsplash.com/photo-${photo}?q=80&w=800&auto=format&fit=crop`;

const COVERS: Record<string, string> = {
  'Nha Trang': cover('1544644181-1484b3fdfc62'),
  'Phú Quốc': cover('1506744038136-46273834b3fb'),
  'Đà Nẵng': cover('1559592413-7cec4d0cae2b'),
  'Hội An': cover('1559592413-7cec4d0cae2b'),
  'TP. Hồ Chí Minh': cover('1583417319070-4a69db38a482'),
  'Hạ Long': cover('1528127269322-539801943592'),
  'Quy Nhơn': cover('1507525428034-b723cf961d3e'),
  'Đà Lạt': cover('1519681393784-d120267933ba'),
};

export function coverFor(destination: string): string | null {
  return COVERS[destination] ?? null;
}
