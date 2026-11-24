# Báo cáo tiến độ Tuần 1 — Đề tài: Hệ thống chấm bài trực tuyến (Online Judge)

**Thời gian:** tuần 16/11/2026 – 20/11/2026

**Tình trạng:** đã hoàn thành phần lập kế hoạch và khung dự án.

## 1. Công việc đã hoàn thành

### Lập kế hoạch

- Xác định phạm vi phiên bản đầu tiên:
  - quản lý kỳ thi và danh sách bài tập kèm điểm;
  - nộp bài và chấm tự động, có tính điểm từng phần theo số test đúng;
  - quản trị viên tải lên bộ test.
- Ngôn ngữ hỗ trợ ban đầu: C++ và Python.
- Phân công 3 thành viên theo 3 phần độc lập:
  - Backend: API và cơ sở dữ liệu;
  - Bộ chấm bài: biên dịch, chạy chương trình và đưa ra kết quả;
  - Giao diện web.
- Viết đặc tả chung để 3 phần ghép lại được với nhau. Đặc tả gồm cấu trúc cơ sở dữ liệu, các API kèm dữ liệu mẫu, và quy tắc chấm điểm (AC, WA, TLE, MLE, RE, CE).
- Lập kế hoạch 6 tuần:
  - Tuần 1–3: hoàn thành phiên bản cơ bản.
  - Tuần 4–5: bổ sung tính năng, ví dụ:
    - bảng xếp hạng;
    - chạy thử với dữ liệu tự nhập;
    - giới hạn thời gian kỳ thi;
    - nhập danh sách sinh viên và xuất bảng điểm ra Excel;
    - kiểm tra đạo văn.
  - Tuần 6: kiểm thử tổng thể và chuẩn bị demo.

### Xây dựng khung dự án (đã đưa lên GitHub)

- Toàn bộ hệ thống (cơ sở dữ liệu, backend, bộ chấm, giao diện) khởi động bằng một lệnh nhờ Docker.
- Backend dùng FastAPI. Đã có API kiểm tra trạng thái hệ thống và định dạng lỗi thống nhất.
- Cơ sở dữ liệu PostgreSQL: 7 bảng của phiên bản cơ bản được tạo tự động khi khởi động.
- Bộ chấm bài chạy trong môi trường bị chặn Internet, để chương trình do sinh viên nộp không truy cập ra ngoài được.
- Mỗi lần đẩy code lên GitHub, hệ thống tự động kiểm tra chất lượng code, chạy kiểm thử và khởi động thử toàn bộ hệ thống.
- 14 bài kiểm thử tự động của backend đều đạt, độ bao phủ 95%.

## 2. Công việc chưa hoàn thành

| Hạng mục | Phụ trách | Dự kiến |
|---|---|---|
| Đăng nhập | Backend | Đầu tuần 2 |
| Dữ liệu mẫu (tài khoản, kỳ thi, 5 bài tập) | Backend | Đầu tuần 2 |
| API danh sách kỳ thi | Backend | Tuần 2 |
| Bộ chấm bài thực tế (hiện mới có khung) | Bộ chấm | Tuần 2 |
| Giao diện web thực tế (hiện mới có trang tạm) | Giao diện | Tuần 2 |

## 3. Mục tiêu tuần 2

Chạy được trọn vẹn một luồng: sinh viên đăng nhập, vào kỳ thi, nộp bài, hệ thống chấm và báo **Accepted**, rồi điểm được cập nhật trong danh sách bài tập.
