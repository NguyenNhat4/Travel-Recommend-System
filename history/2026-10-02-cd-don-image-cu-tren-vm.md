# Dọn image cũ trên VM sau mỗi lần deploy backend/frontend

- Ngày: 2026-10-02
- Tác giả: người dùng / Claude
- Nhánh: feat/cd-prune-old-images
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

VM app 10 GB đầy dần: mỗi lần CD pull image mới theo digest nhưng không bao giờ xoá image cũ. Thêm bước dọn vào script deploy chạy trên VM.

## File thay đổi

- `scripts/deploy-backend-vm.sh`: thêm `prune_old_images` sau khi deploy healthy.
- `scripts/deploy-frontend-vm.sh`: như trên cho frontend.

## Quyết định

- Chỉ xoá image cùng repository với image vừa deploy, giữ image mới và image ngay trước (rollback tay). Image đang có container dùng thì `docker rmi` tự từ chối.
- Không dùng `docker image prune -a` hay `prune -f` toàn cục: image crawler pin theo digest (không tag) và chạy bằng `docker run --rm`, nên bị coi là unused/dangling và sẽ bị xoá nhầm, làm cron `PULL=0` lỗi.
- Lỗi dọn không làm fail deploy (`|| true`).

## Kiểm tra

- `bash -n` hai script: OK.
- `scripts/tests/test-backend-vm-cd-sync.sh`: pass.
- Chưa chạy trên VM thật.

## Việc còn lại

- Giới hạn log Docker (`daemon.json` max-size/max-file), journald, và rotation log/data của crawler chưa làm.
