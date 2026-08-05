import api from './api'
import type { FileAsset, FileAssetListResponse, FileUploadIntent, FileUploadIntentPayload } from './types'

export interface UploadProgressUpdate {
  loaded: number
  total: number
  stage: 'uploading' | 'confirming'
}

export async function createUploadIntent(payload: FileUploadIntentPayload): Promise<FileUploadIntent> {
  const { data } = await api.post<FileUploadIntent>('/files/upload-intents', payload)
  return data
}

export async function uploadFile(
  file: File,
  onProgress?: (update: UploadProgressUpdate) => void,
): Promise<FileAsset> {
  const intent = await createUploadIntent({
    filename: file.name,
    size_bytes: file.size,
  })

  if (intent.upload.kind === 'local') {
    const form = new FormData()
    form.append('file', file, file.name)
    await api.post(intent.upload.url, form, {
      onUploadProgress: (event) => onProgress?.({
        // The browser has sent the request body at 100%, but FastAPI may still
        // be receiving and writing it to disk. Reserve the final slice for that
        // server-side work so the UI does not falsely claim completion.
        loaded: Math.min(event.loaded, Math.floor(file.size * 0.95)),
        total: event.total ?? file.size,
        stage: event.total && event.loaded >= event.total ? 'confirming' : 'uploading',
      }),
    })
  } else {
    await uploadToS3(intent, file, onProgress)
  }

  onProgress?.({ loaded: file.size, total: file.size, stage: 'confirming' })
  const { data } = await api.post<FileAsset>(`/files/${intent.asset.id}/complete`)
  return data
}

function uploadToS3(
  intent: FileUploadIntent,
  file: File,
  onProgress?: (update: UploadProgressUpdate) => void,
): Promise<void> {
  if (intent.upload.kind !== 's3_post') {
    return Promise.reject(new Error('无效的对象存储上传目标'))
  }
  const target = intent.upload

  return new Promise((resolve, reject) => {
    const form = new FormData()
    Object.entries(target.fields).forEach(([key, value]) => form.append(key, value))
    form.append('file', file)

    const request = new XMLHttpRequest()
    request.open('POST', target.url)
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.({ loaded: event.loaded, total: event.total, stage: 'uploading' })
      }
    }
    request.onerror = () => reject(new Error('对象存储上传网络错误'))
    request.onabort = () => reject(new Error('对象存储上传已取消'))
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve()
      } else {
        reject(new Error(`对象存储拒绝了文件上传（${request.status}）`))
      }
    }
    request.send(form)
  })
}

export async function listFiles(): Promise<FileAssetListResponse> {
  const { data } = await api.get<FileAssetListResponse>('/files')
  return data
}

export async function deleteFile(assetId: string): Promise<FileAsset> {
  const { data } = await api.delete<FileAsset>(`/files/${assetId}`)
  return data
}

export async function downloadFile(asset: FileAsset): Promise<void> {
  const { data } = await api.get<Blob>(`/files/${asset.id}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = asset.original_filename
  anchor.click()
  URL.revokeObjectURL(url)
}
