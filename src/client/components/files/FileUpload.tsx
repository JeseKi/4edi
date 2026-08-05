import { UploadOutlined } from '@ant-design/icons'
import { App, Button, Empty, Flex, Image, List, Modal, Progress, Space, Tag, Typography, Upload } from 'antd'
import type { UploadFile } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { uploadFile } from '../../lib/files'
import { resolveApiErrorMessage } from '../../lib/error'
import type { FileAsset } from '../../lib/types'

const MAX_CONCURRENT_UPLOADS = 3

type TransferStatus = 'queued' | 'uploading' | 'confirming' | 'error'

interface TransferItem {
  id: string
  file: File
  loaded: number
  status: TransferStatus
  startedAt?: number
  error?: string
}

interface FileUploadProps {
  accept?: string
  disabled?: boolean
  onUploaded?: (asset: FileAsset) => void
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  if (seconds < 60) return `${Math.ceil(seconds)} 秒`
  return `${Math.floor(seconds / 60)} 分 ${Math.ceil(seconds % 60)} 秒`
}

async function getPreviewImage(file: UploadFile): Promise<string> {
  if (file.url) return file.url
  const source = file.originFileObj
  if (!source) return ''
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.readAsDataURL(source)
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('无法生成文件预览'))
  })
}

export default function FileUpload({ accept, disabled, onUploaded }: FileUploadProps) {
  const { message } = App.useApp()
  const [selectionOpen, setSelectionOpen] = useState(false)
  const [progressOpen, setProgressOpen] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<UploadFile[]>([])
  const [transfers, setTransfers] = useState<TransferItem[]>([])
  const [totalBytes, setTotalBytes] = useState(0)
  const [completedBytes, setCompletedBytes] = useState(0)
  const [completedCount, setCompletedCount] = useState(0)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const uploadingRef = useRef(false)

  const hasActiveTransfer = transfers.some((item) => item.status !== 'error')
  const totalLoaded = completedBytes + transfers.reduce((sum, item) => sum + item.loaded, 0)
  const elapsedSeconds = startedAt ? Math.max((now - startedAt) / 1000, 0.1) : 0
  const speed = totalLoaded / elapsedSeconds
  const remainingBytes = transfers
    .filter((item) => item.status !== 'error')
    .reduce((sum, item) => sum + Math.max(item.file.size - item.loaded, 0), 0)
  const totalPercent = totalBytes ? Math.round((totalLoaded / totalBytes) * 100) : 0
  const failedCount = transfers.filter((item) => item.status === 'error').length

  useEffect(() => {
    if (!progressOpen || !hasActiveTransfer) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(timer)
  }, [hasActiveTransfer, progressOpen])

  const selectionSummary = useMemo(
    () => `${selectedFiles.length} 个文件，共 ${formatBytes(selectedFiles.reduce((sum, item) => sum + (item.size ?? 0), 0))}`,
    [selectedFiles],
  )

  const startUploads = async () => {
    const entries = selectedFiles.flatMap((item): TransferItem[] => {
      const file = item.originFileObj
      return file ? [{ id: item.uid, file, loaded: 0, status: 'queued' }] : []
    })
    if (!entries.length) return

    setSelectionOpen(false)
    setProgressOpen(true)
    setSelectedFiles([])
    setTransfers(entries)
    setTotalBytes(entries.reduce((sum, item) => sum + item.file.size, 0))
    setCompletedBytes(0)
    setCompletedCount(0)
    setStartedAt(Date.now())
    setNow(Date.now())
    uploadingRef.current = true

    let nextIndex = 0
    const uploadOne = async (item: TransferItem) => {
      setTransfers((current) => current.map((entry) => (
        entry.id === item.id ? { ...entry, status: 'uploading', startedAt: Date.now() } : entry
      )))
      try {
        const asset = await uploadFile(item.file, (update) => {
          setTransfers((current) => current.map((entry) => (
            entry.id === item.id
              ? { ...entry, loaded: Math.min(update.loaded, entry.file.size), status: update.stage }
              : entry
          )))
        })
        setCompletedBytes((current) => current + item.file.size)
        setCompletedCount((current) => current + 1)
        setTransfers((current) => current.filter((entry) => entry.id !== item.id))
        onUploaded?.(asset)
      } catch (error) {
        const errorMessage = resolveApiErrorMessage(error, '文件上传失败，请稍后重试。')
        setTransfers((current) => current.map((entry) => (
          entry.id === item.id
            ? { ...entry, status: 'error', error: errorMessage }
            : entry
        )))
        message.error(`${item.file.name}：${errorMessage}`)
      }
    }

    const worker = async () => {
      while (nextIndex < entries.length) {
        const item = entries[nextIndex]
        nextIndex += 1
        await uploadOne(item)
      }
    }

    await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT_UPLOADS, entries.length) }, worker))
    uploadingRef.current = false
    setNow(Date.now())
  }

  const closeProgress = () => {
    if (!uploadingRef.current) setProgressOpen(false)
  }

  return (
    <>
      <Button icon={<UploadOutlined />} disabled={disabled} onClick={() => setSelectionOpen(true)}>上传文件</Button>

      <Modal
        destroyOnClose
        open={selectionOpen}
        title="选择要上传的文件"
        width={760}
        okButtonProps={{ disabled: !selectedFiles.length }}
        okText="开始上传"
        onCancel={() => setSelectionOpen(false)}
        onOk={() => void startUploads()}
      >
        <Typography.Paragraph type="secondary">可一次选择多个文件。确认后将最多同时上传 {MAX_CONCURRENT_UPLOADS} 个文件。</Typography.Paragraph>
        <Upload.Dragger
          accept={accept}
          beforeUpload={() => false}
          fileList={selectedFiles}
          listType="picture-card"
          multiple
          onChange={({ fileList }) => setSelectedFiles(fileList)}
          onPreview={(file) => {
            if (file.type?.startsWith('image/')) {
              void getPreviewImage(file).then(setPreviewImage)
            }
          }}
        >
          <p className="ant-upload-drag-icon"><UploadOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处</p>
          <p className="ant-upload-hint">服务器会在上传前校验文件类型和大小。</p>
        </Upload.Dragger>
        {selectedFiles.length > 0 && <Typography.Text type="secondary">已选择：{selectionSummary}</Typography.Text>}
      </Modal>

      {previewImage && (
        <Image
          preview={{
            visible: true,
            src: previewImage,
            onVisibleChange: (visible) => { if (!visible) setPreviewImage(null) },
          }}
          src={previewImage}
          style={{ display: 'none' }}
        />
      )}

      <Modal
        closable={!uploadingRef.current}
        maskClosable={!uploadingRef.current}
        open={progressOpen}
        title="上传进度"
        width={720}
        footer={uploadingRef.current ? null : <Button onClick={closeProgress}>关闭</Button>}
        onCancel={closeProgress}
      >
        <Flex vertical gap={12}>
          <Progress percent={Math.min(totalPercent, 100)} status={failedCount ? 'exception' : undefined} />
          <Space wrap>
            <Typography.Text>已完成 {completedCount} 个文件</Typography.Text>
            <Typography.Text type="secondary">{formatBytes(totalLoaded)} / {formatBytes(totalBytes)}</Typography.Text>
            <Typography.Text type="secondary">{formatBytes(speed)}/s</Typography.Text>
            <Typography.Text type="secondary">预计剩余 {hasActiveTransfer ? formatDuration(remainingBytes / Math.max(speed, 1)) : '—'}</Typography.Text>
          </Space>
          {transfers.length ? (
            <List
              size="small"
              dataSource={transfers}
              renderItem={(item) => {
                const percent = item.file.size ? Math.round((item.loaded / item.file.size) * 100) : 0
                const label = item.status === 'confirming' ? '服务端确认中' : item.status === 'error' ? '上传失败' : item.status === 'queued' ? '等待上传' : '上传中'
                const itemElapsed = item.startedAt ? Math.max((now - item.startedAt) / 1000, 0.1) : 0
                const itemSpeed = item.loaded / itemElapsed
                const itemRemaining = Math.max(item.file.size - item.loaded, 0) / Math.max(itemSpeed, 1)
                return (
                  <List.Item>
                    <Flex vertical gap={4} style={{ width: '100%' }}>
                      <Flex justify="space-between" gap={12}>
                        <Typography.Text ellipsis>{item.file.name}</Typography.Text>
                        <Tag color={item.status === 'error' ? 'error' : item.status === 'confirming' ? 'processing' : 'blue'}>{label}</Tag>
                      </Flex>
                      <Progress percent={percent} size="small" status={item.status === 'error' ? 'exception' : undefined} />
                      {item.status !== 'error' && item.status !== 'queued' && <Typography.Text type="secondary">{formatBytes(itemSpeed)}/s · 剩余 {formatDuration(itemRemaining)}</Typography.Text>}
                      {item.error && <Typography.Text type="danger">{item.error}</Typography.Text>}
                    </Flex>
                  </List.Item>
                )
              }}
            />
          ) : (
            <Empty description={completedCount ? '全部文件上传完成' : '没有待展示的上传任务'} image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Flex>
      </Modal>
    </>
  )
}
