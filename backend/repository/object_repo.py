import logging
from typing import Optional, Union, BinaryIO
from qcloud_cos import CosConfig as TencentCosConfig
from qcloud_cos import CosS3Client
from backend.core.config import settings

logger = logging.getLogger(__name__)

class ObjectStorageRepository:
    """
    用于与腾讯云对象存储 (COS) 交互的仓库类。
    """
    def __init__(self):
        self.config = settings.cos
        self.client: Optional[CosS3Client] = None
        
        #客户端配置
        if self.config.enabled:
            if self.config.secret_id and self.config.secret_key:
                try:
                    conf = TencentCosConfig(
                        Region=self.config.region, 
                        SecretId=self.config.secret_id, 
                        SecretKey=self.config.secret_key, 
                        Token=None, 
                        Scheme=self.config.scheme
                    )
                    self.client = CosS3Client(conf)
                    logger.info(f"Tencent COS client initialized for bucket: {self.config.bucket}")
                except Exception as e:
                    logger.error(f"Failed to initialize Tencent COS client: {e}")
                    self.client = None
            else:
                logger.warning("COS enabled but credentials (secret_id/secret_key) are missing.")
        else:
            logger.debug("COS is disabled in configuration.")

    def upload_file(self, file_content: Union[bytes, str, BinaryIO], key: str, content_type: str = None) -> bool:
        """
        文件上传到 COS
        :param file_content: 文件内容（字节、字符串或类文件对象）
        :param key: 对象键（存储桶中的路径）
        :param content_type: 文件的 MIME 类型
        :return: 如果上传成功则返回 True，否则返回 False
        """
        if not self.client:
            logger.warning("COS client is not ready. Cannot upload file.")
            return False
            
        try:
            # CosS3Client.put_object 接受字符串、字节或流
            self.client.put_object(
                Bucket=self.config.bucket,
                Body=file_content,
                Key=key,
                ContentType=content_type,
                EnableMD5=False
            )
            logger.info(f"Successfully uploaded file to COS: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload file to COS (key={key}): {e}")
            return False

    def get_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """
        生成用于下载文件的预签名 URL。
        :param key: 对象键
        :param expiration: 过期时间，单位秒（默认为 1 小时）
        :return: 预签名 URL 字符串，如果客户端未准备好则返回 None
        """
        if not self.client:
            return None
        
        try:
            url = self.client.get_presigned_url(
                Method='GET',
                Bucket=self.config.bucket,
                Key=key,
                Expired=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return None

    def get_public_url(self, key: str) -> Optional[str]:
        """
        返回文件的公共 URL（假设存储桶/文件支持公共访问）。
        不检查是否存在或签名请求。
        """
        if not self.config.enabled:
             return None
        # Standard format: https://<BucketName-APPID>.cos.<Region>.myqcloud.com/<Key>
        return f"{self.config.scheme}://{self.config.bucket}.cos.{self.config.region}.myqcloud.com/{key}"

    def delete_file(self, key: str) -> bool:
        """
        从 COS 中删除文件。
        :param key: 对象键
        :return: 如果删除命令发送成功则返回 True
        """
        if not self.client:
            return False
            
        try:
            self.client.delete_object(
                Bucket=self.config.bucket,
                Key=key
            )
            logger.info(f"Successfully deleted file from COS: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {key} from COS: {e}")
            return False

    def file_exists(self, key: str) -> bool:
        """
        检查文件是否存在于 COS 中。
        :param key: 对象键
        :return: 如果存在则返回 True，否则返回 False
        """
        if not self.client:
            return False

        try:
            # 如果对象不存在 (404)，head_object 会抛出 CosServiceError
            self.client.head_object(
                Bucket=self.config.bucket,
                Key=key
            )
            return True
        except Exception:
            return False

    def download_file(self, key: str, local_path: str) -> bool:
        """
        从 COS 下载文件到本地。
        :param key: 对象键
        :param local_path: 本地保存路径
        :return: 成功返回 True
        """
        if not self.client:
            return False
            
        try:
            response = self.client.get_object(
                Bucket=self.config.bucket,
                Key=key
            )
            with open(local_path, 'wb') as f:
                f.write(response['Body'].get_raw_stream().read())
            logger.info(f"Successfully downloaded {key} from COS to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download file from COS (key={key}): {e}")
            return False

# 单例实例，便于导入
object_storage = ObjectStorageRepository()
