import { useCallback, useEffect, useState } from 'react'
import { App, Button, Card, Flex, List, Popconfirm, Space, Typography } from 'antd'
import FileUpload from '../../../components/files/FileUpload'
import { deleteFile, downloadFile, listFiles } from '../../../lib/files'
import type { FileAsset } from '../../../lib/types'
import { resolveErrorMessage } from './utils'

function displaySize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`
}

export default function FileAssetsCard() {
  const { message } = App.useApp()
  const [assets, setAssets] = useState<FileAsset[]>([])
  const [loading, setLoading] = useState(false)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listFiles()
      setAssets(result.items.filter((asset) => asset.status === 'available'))
    } catch (error) {
      message.error(resolveErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void refresh() }, [refresh])

  const remove = async (asset: FileAsset) => {
    try {
      await deleteFile(asset.id)
      setAssets((current) => current.filter((item) => item.id !== asset.id))
      message.success('文件已进入删除队列')
    } catch (error) {
      message.error(resolveErrorMessage(error))
    }
  }

  const download = async (asset: FileAsset) => {
    setDownloadingId(asset.id)
    try {
      await downloadFile(asset)
      message.success(`${asset.original_filename} 下载完成`)
    } catch (error) {
      message.error(`${asset.original_filename}：${resolveErrorMessage(error)}`)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <Card title="文件上传示例" extra={<FileUpload onUploaded={() => void refresh()} />}>
      <Typography.Paragraph type="secondary">支持本地磁盘开发模式与 S3 预签名直传；默认仅当前用户和管理员可访问。</Typography.Paragraph>
      <List
        loading={loading}
        dataSource={assets}
        locale={{ emptyText: '尚未上传文件' }}
        renderItem={(asset) => (
          <List.Item
            actions={[
              <Button
                key="download"
                loading={downloadingId === asset.id}
                type="link"
                onClick={() => void download(asset)}
              >
                下载
              </Button>,
              <Popconfirm key="delete" title="确认删除此文件？" onConfirm={() => void remove(asset)}>
                <Button danger type="link">删除</Button>
              </Popconfirm>,
            ]}
          >
            <Flex vertical>
              <Typography.Text>{asset.original_filename}</Typography.Text>
              <Space size={8}><Typography.Text type="secondary">{displaySize(asset.size_bytes)}</Typography.Text></Space>
            </Flex>
          </List.Item>
        )}
      />
    </Card>
  )
}
