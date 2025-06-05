from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, sp
from astrbot.api.all import *
from typing import Dict, Optional


@register(
    "msgdistributor",
    "Dinggg",
    "根据群id/好友名/好友id动态选择Provider的插件",
    "1.0.0",
    "https://github.com/AAlexDing/astrbot_plugin_msgdistributor",
)
class MsgDistributor(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化映射配置
        self.platform_group_provider_map: Dict[str, Dict[str, str]] = {}  # platform -> {group_id: provider_id}
        self.platform_friend_provider_map: Dict[str, Dict[str, str]] = {}   # platform -> {user_name: provider_id}

        # 从配置加载映射关系
        for mapping in config.get("platform_group_provider_map", []):
            try:
                platform, group_name, provider_id = mapping.split("::")
                if platform not in self.platform_group_provider_map:
                    self.platform_group_provider_map[platform] = {}
                self.platform_group_provider_map[platform][group_name] = provider_id
            except ValueError:
                logger.error(f"Invalid group mapping format: {mapping}")

        for mapping in config.get("platform_friend_provider_map", []):
            try:
                platform, user_name, provider_id = mapping.split("::")
                if platform not in self.platform_friend_provider_map:
                    self.platform_friend_provider_map[platform] = {}
                self.platform_friend_provider_map[platform][user_name] = provider_id
            except ValueError:

                logger.error(f"Invalid user mapping format: {mapping}")

    def _get_default_provider(self, platform: str) -> Optional[Provider]:
        """根据平台获取默认的Provider实例"""
        return self.context.get_provider_by_id(self.config.get("default_provider", ""))

    def _get_provider_for_group(self, platform: str, group_name: str) -> Optional[Provider]:
        """根据平台和群名获取对应的Provider实例"""
        if platform in self.platform_group_provider_map and group_name in self.platform_group_provider_map[platform]:
            provider_id = self.platform_group_provider_map[platform][group_name]
            return self.context.get_provider_by_id(provider_id)
        return None

    def _get_provider_for_user(self, platform: str, user_name: str) -> Optional[Provider]:
        """根据平台和用户名获取对应的Provider实例"""
        if platform in self.platform_friend_provider_map and user_name in self.platform_friend_provider_map[platform]:
            provider_id = self.platform_friend_provider_map[platform][user_name]
            return self.context.get_provider_by_id(provider_id)
        return None

    def _set_curr_provider(self, provider: Provider):
        """设置当前的Provider"""
        self.context.provider_manager.curr_provider_inst = provider
        sp.put("curr_provider", provider.meta().id)
        if not self.context.get_using_provider():
            logger.warning("No provider is currently enabled.")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息，在LLM调用前设置对应的Provider"""
        if not self.config.get("enable_distribute", False):
            return

        # 只处理需要LLM回复的消息
        if not event.is_at_or_wake_command:
            return

        platform = event.get_platform_id()
        group_id = event.message_obj.group_id

        if not group_id:
            return

        provider = self._get_provider_for_group(platform, group_id)
        if provider:
            self._set_curr_provider(provider)
            logger.info(f"消息分发：平台 {platform} - 群ID {group_id} 使用Provider {provider.meta().id}")
        else:
            default_provider = self._get_default_provider(platform)
            if default_provider:
                self._set_curr_provider(default_provider)
                logger.info(f"消息分发：平台 {platform} - 群ID {group_id} 使用默认Provider")
            else:
                logger.info(f"消息分发：平台 {platform} - 群ID {group_id} 使用系统Provider")

    @filter.event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """处理私聊消息，在LLM调用前设置对应的Provider"""

        if not self.config.get("enable_distribute", False):
            return

        # 只处理需要LLM回复的消息
        if not event.is_at_or_wake_command:
            return

        platform = event.get_platform_id()
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()

        if not user_name and not user_id:
            return

        provider_by_name = self._get_provider_for_user(platform, user_name)
        provider_by_id = self._get_provider_for_user(platform, user_id)
        if provider_by_id or provider_by_name:
            provider = provider_by_id or provider_by_name
            self._set_curr_provider(provider)
            logger.info(f"消息分发：平台 {platform} - 用户名 {user_name} / 用户ID {user_id} 使用Provider {provider.meta().id}")
        else:
            default_provider = self._get_default_provider(platform)
            if default_provider:
                self._set_curr_provider(default_provider)
                logger.info(f"消息分发：平台 {platform} - 用户名 {user_name} / 用户ID {user_id} 使用默认Provider")
            else:
                logger.info(f"消息分发：平台 {platform} - 用户名 {user_name} / 用户ID {user_id} 使用系统Provider")

