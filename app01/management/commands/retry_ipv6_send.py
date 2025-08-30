from django.core.management.base import BaseCommand
from django.utils import timezone
from app01 import models
from app01.utils.ipv6_api import send_to_kea_api
import json
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '手动重试发送失败的IPv6地址到KEA API（已移除自动定时重试功能）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-failed',
            action='store_true',
            help='清理所有失败记录的重试时间字段'
        )

    def handle(self, *args, **options):
        current_time = timezone.now()
        
        # 如果指定清理选项，清理所有失败记录的重试时间
        if options['clear_failed']:
            updated = models.PrettyNum.objects.filter(
                send_status='failed'
            ).update(
                next_retry_time=None,
                retry_count=0
            )
            self.stdout.write(
                self.style.SUCCESS(f"已清理 {updated} 个失败记录的重试信息")
            )
            return
        
        # 查找失败的IPv6记录（移除定时重试逻辑）
        # 注意：pending状态是等待API回调，不要重试
        failed_records = models.PrettyNum.objects.filter(
            send_status__in=['failed', 'retrying']
        )
        
        self.stdout.write(f"找到 {failed_records.count()} 个失败的IPv6记录，准备手动重试")
        
        success_count = 0
        failed_count = 0
        
        for ipv6_obj in failed_records:
            self.stdout.write(f"重试发送 IPv6: {ipv6_obj.ipv6_address}, MAC: {ipv6_obj.mac_address}")
            
            try:
                # 更新状态为重试中
                ipv6_obj.send_status = 'retrying'
                ipv6_obj.retry_count += 1
                ipv6_obj.last_send_time = current_time
                ipv6_obj.save()
                
                # 调用KEA API（重试时不需要回调URL，因为我们直接处理结果）
                result = send_to_kea_api(ipv6_obj.id, ipv6_obj.ipv6_address, ipv6_obj.mac_address)
                
                # 更新API响应
                ipv6_obj.api_response = json.dumps(result['response_data']) if result['response_data'] else result.get('error', '')
                
                if result['success']:
                    # 重试成功
                    ipv6_obj.send_status = 'success'
                    ipv6_obj.next_retry_time = None  # 清除重试时间
                    ipv6_obj.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ IPv6地址 {ipv6_obj.ipv6_address} 手动重试发送成功（第{ipv6_obj.retry_count}次重试）"
                        )
                    )
                    success_count += 1
                    
                else:
                    # 重试仍然失败，但不再设置自动重试时间
                    ipv6_obj.send_status = 'failed'
                    ipv6_obj.next_retry_time = None  # 移除自动重试时间设置
                    ipv6_obj.save()
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f"❌ IPv6地址 {ipv6_obj.ipv6_address} 第{ipv6_obj.retry_count}次重试失败，需要手动重试"
                        )
                    )
                    failed_count += 1
                    
            except Exception as e:
                # 重试过程中出现异常
                ipv6_obj.send_status = 'failed'
                ipv6_obj.api_response = f"重试异常: {str(e)}"
                ipv6_obj.next_retry_time = None  # 移除自动重试时间设置
                ipv6_obj.save()
                failed_count += 1
                
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ IPv6地址 {ipv6_obj.ipv6_address} 重试时出现异常: {str(e)}"
                    )
                )
                logger.error(f"手动重试IPv6发送异常: {e}", exc_info=True)
        
        # 输出汇总信息
        self.stdout.write(
            self.style.SUCCESS(
                f"\n手动重试任务完成！"
                f"\n成功: {success_count} 个"
                f"\n失败: {failed_count} 个"
                f"\n注意：已移除自动定时重试功能，如需重试失败记录请手动执行此命令"
            )
        )
