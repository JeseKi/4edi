import { useCallback, useEffect, useState } from 'react'
import { Alert, App, Button, Checkbox, Descriptions, Form, Image, Input, Modal, Space, Spin, Steps, Tag } from 'antd'
import FileUpload from '../../../components/files/FileUpload'
import CurrentLegalConsent from '../../../components/legal/CurrentLegalConsent'
import {
  acceptMerchantAgreement,
  applyMallShop,
  getMyShopAgreement,
  getMyMallShop,
  resubmitMallShopQualification,
  submitMerchantSignedAgreement,
  updateMallShop,
  type MallShopApplicationPayload,
} from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import api from '../../../lib/api'
import type { MallShop, ShopAgreement, ShopOnboardingStage } from '../../../lib/types'
import { sellerAgreementAction, sellerOnboardingStepIndex } from './agreementActions'
import ShopQualificationForm from './ShopQualificationForm'

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '入驻处理中', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

const ONBOARDING_STEPS = [
  { title: '提交资质' },
  { title: '平台审核' },
  { title: '在线签约' },
  { title: '审核通过' },
]

const ONLINE_STAGE_NOTICES: Partial<Record<ShopOnboardingStage, string>> = {
  qualification_submitted: '资质已提交，平台将人工核验企业登记信息。',
  qualification_preapproved: '资质预审已通过，系统正在生成电子协议。',
  agreement_generated: '资质预审已通过，请阅读完整协议并在线确认签署。',
  agreement_archived: '商家已在线签约，电子协议已归档，等待平台最终审核。',
  approved: '商家审核已通过，可以开始经营。',
}

const LEGACY_STAGE_NOTICES: Partial<Record<ShopOnboardingStage, string>> = {
  ...ONLINE_STAGE_NOTICES,
  agreement_generated: '历史协议定稿已生成，请完成商家签署并上传。',
  merchant_signed: '商家签署文件已提交，等待平台核对并签署。',
  platform_signed: '平台已签署，等待将双方签署的最终协议归档。',
  agreement_archived: '最终协议已归档，等待平台完成最终入驻批准。',
}

export default function ShopManagePage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [shop, setShop] = useState<MallShop | null>(null)
  const [agreement, setAgreement] = useState<ShopAgreement | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [merchantSignedAssetId, setMerchantSignedAssetId] = useState('')
  const [agreementConfirmed, setAgreementConfirmed] = useState(false)
  const [signedAgreementPreview, setSignedAgreementPreview] = useState<{ url: string; contentType: string; filename: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const nextShop = await getMyMallShop()
      setShop(nextShop)
      setAgreement(nextShop.current_agreement_id ? await getMyShopAgreement() : null)
    } catch {
      setShop(null)
      setAgreement(null)
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { void load() }, [load])

  const submitQualification = async (payload: MallShopApplicationPayload) => {
    setSaving(true)
    try {
      setShop(shop ? await resubmitMallShopQualification(payload) : await applyMallShop(payload))
      setAgreement(null)
      message.success('资质已提交，等待平台预审')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提交失败'))
    } finally {
      setSaving(false)
    }
  }

  const submitSignedAgreement = async () => {
    if (!agreement || !shop) return
    if (!merchantSignedAssetId || !agreementConfirmed) {
      message.error('请上传签署文件并确认协议编号与版本')
      return
    }
    setSaving(true)
    try {
      setShop(await submitMerchantSignedAgreement({
        agreement_number: agreement.agreement_number,
        document_version: agreement.document_version,
        merchant_signed_asset_id: merchantSignedAssetId,
        confirmed: true,
      }))
      setAgreement(await getMyShopAgreement())
      message.success('商家签署文件已提交，等待平台签署')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提交失败'))
    } finally {
      setSaving(false)
    }
  }

  const acceptAgreement = async () => {
    if (!agreement || !agreementConfirmed) {
      message.error('请先阅读完整协议并勾选确认')
      return
    }
    setSaving(true)
    try {
      setShop(await acceptMerchantAgreement({
        agreement_number: agreement.agreement_number,
        document_version: agreement.document_version,
        draft_content_sha256: agreement.draft_content_sha256,
        confirmed: true,
      }))
      setAgreement(await getMyShopAgreement())
      setAgreementConfirmed(false)
      message.success('电子协议已签署并归档，等待平台最终审核')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '电子协议签署失败'))
    } finally {
      setSaving(false)
    }
  }

  const saveEdit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      setShop(await updateMallShop(values))
      setEditOpen(false)
      message.success('店铺信息已更新')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const previewSignedAgreement = async () => {
    if (!agreement) return
    try {
      const { data } = await api.get<Blob>('/mall/seller/shop/agreement/signed-file', {
        responseType: 'blob',
      })
      const extension = data.type === 'application/pdf'
        ? '.pdf'
        : data.type === 'image/png'
          ? '.png'
          : data.type === 'image/jpeg'
            ? '.jpg'
            : ''
      setSignedAgreementPreview({
        url: URL.createObjectURL(data),
        contentType: data.type,
        filename: `双方签署协议-${agreement.agreement_number}${extension}`,
      })
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '双方签署协议加载失败'))
    }
  }

  const closeSignedAgreementPreview = () => {
    if (signedAgreementPreview) URL.revokeObjectURL(signedAgreementPreview.url)
    setSignedAgreementPreview(null)
  }

  const downloadSignedAgreement = () => {
    if (!signedAgreementPreview) return
    const anchor = document.createElement('a')
    anchor.href = signedAgreementPreview.url
    anchor.download = signedAgreementPreview.filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  }

  if (loading) return <div className="flex justify-center py-24"><Spin size="large" /></div>
  const canSubmit = !shop || (shop.status !== 'pending' && !shop.platform_verified)
  const agreementAction = shop && agreement
    ? sellerAgreementAction(shop.onboarding_stage, agreement.signature_mode)
    : null
  const stageNotices = agreement?.signature_mode === 'uploaded_document'
    ? LEGACY_STAGE_NOTICES
    : ONLINE_STAGE_NOTICES

  return (
    <div className="space-y-4">
      <CurrentLegalConsent />
      {canSubmit && (
        <div className="rounded bg-white p-6" style={{ maxWidth: 680 }}>
          <h3 className="text-base font-bold mb-2">{shop ? '重新提交店铺资质' : '申请开店'}</h3>
          {shop?.reject_reason && <Alert className="mb-4" type="error" showIcon message={shop.reject_reason} />}
          <ShopQualificationForm
            saving={saving}
            submitLabel={shop ? '重新提交审核' : '提交申请'}
            initialValues={shop ? {
              name: shop.name,
              description: shop.description,
              legal_entity_name: shop.legal_entity_name,
              unified_social_credit_code: shop.unified_social_credit_code,
              legal_representative: shop.legal_representative,
              registered_address: shop.registered_address,
              business_address: shop.business_address,
              contact_phone: shop.contact_phone,
              real_name: shop.real_name,
            } : undefined}
            onSubmit={submitQualification}
          />
        </div>
      )}

      {shop && (
        <div className="rounded bg-white p-6 space-y-4">
          <div className="flex items-center justify-between"><h3 className="text-base font-bold">店铺与资质状态</h3><Tag color={STATUS_LABELS[shop.status].color}>{STATUS_LABELS[shop.status].text}</Tag></div>
          <Steps
            size="small"
            responsive
            current={sellerOnboardingStepIndex(shop.onboarding_stage)}
            status={shop.onboarding_stage === 'rejected' ? 'error' : undefined}
            items={ONBOARDING_STEPS.map((item) => ({ title: item.title }))}
          />
          {shop.status === 'pending' && <Alert type="info" showIcon message={stageNotices[shop.onboarding_stage] || '入驻流程正在处理。'} description="最终审核通过前不能发布商品或接单。" />}
          {shop.onboarding_stage === 'rejected' && <Alert type="error" showIcon message="资质预审未通过" description={shop.reject_reason || '请修正资质材料后重新提交。'} />}
          {shop.qualification_state === 'expired' && <Alert type="warning" showIcon message="企业资质复核已过期，店铺和商品已停止公开，请重新提交。" />}
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="店铺名称">{shop.name}</Descriptions.Item>
            <Descriptions.Item label="经营主体">{shop.legal_entity_name || '-'}</Descriptions.Item>
            <Descriptions.Item label="统一社会信用代码">{shop.unified_social_credit_code_masked || '-'}</Descriptions.Item>
            <Descriptions.Item label="法定代表人">{shop.legal_representative || '-'}</Descriptions.Item>
            <Descriptions.Item label="经办人">{shop.real_name || '-'}</Descriptions.Item>
            <Descriptions.Item label="经办人证件">{shop.identity_number_masked || '-'}</Descriptions.Item>
            <Descriptions.Item label="登记状态">{shop.registration_status || '-'}</Descriptions.Item>
            <Descriptions.Item label="当前入驻阶段">{ONBOARDING_STEPS[sellerOnboardingStepIndex(shop.onboarding_stage)].title}</Descriptions.Item>
            <Descriptions.Item label="最近核验">{shop.last_qualification_checked_at || '-'}</Descriptions.Item>
            <Descriptions.Item label="复核有效期">{shop.qualification_valid_until || '-'}</Descriptions.Item>
          </Descriptions>
          {shop.platform_verified && <Button onClick={() => setEditOpen(true)}>编辑店铺展示信息</Button>}
        </div>
      )}

      {shop && agreement && (
        <div className="rounded bg-white p-6 space-y-4">
          <h3 className="text-base font-bold">商家入驻协议</h3>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="协议编号">{agreement.agreement_number}</Descriptions.Item>
            <Descriptions.Item label="协议版本">{agreement.document_version}</Descriptions.Item>
            <Descriptions.Item label="签约方式">{agreement.signature_mode === 'online_click' ? '在线电子签约' : '历史文件签署'}</Descriptions.Item>
            <Descriptions.Item label="协议状态">{stageNotices[shop.onboarding_stage] || agreement.status}</Descriptions.Item>
            {agreement.merchant_signed_at && <Descriptions.Item label="签约时间">{agreement.merchant_signed_at}</Descriptions.Item>}
          </Descriptions>
          {agreement.signature_mode === 'online_click' && (
            <Button href="/mall/seller/agreement/print" target="_blank">
              {agreementAction === 'online_view' ? '查看 / 打印电子协议' : '查看完整电子协议'}
            </Button>
          )}
          {agreement.signature_mode === 'uploaded_document' && (
            <Button href="/mall/seller/agreement/print" target="_blank">查看并打印历史协议正文</Button>
          )}
          {agreementAction === 'legacy_signed_file' && (agreement.final_asset_id || agreement.platform_signed_asset_id) && (
            <Button type="primary" onClick={() => void previewSignedAgreement()}>查看双方签署协议</Button>
          )}
          {agreementAction === 'online_accept' && (
            <div className="space-y-3 rounded border border-solid border-gray-200 p-4">
              <Alert type="info" showIcon message="请先打开并阅读完整电子协议。勾选并确认后，协议立即成立并归档，无需打印、盖章或上传文件。" />
              <div>
                <Checkbox checked={agreementConfirmed} onChange={(event) => setAgreementConfirmed(event.target.checked)}>
                  我已阅读并同意协议全部内容，确认由当前店主账号签署电子协议
                </Checkbox>
              </div>
              <Button type="primary" disabled={!agreementConfirmed} loading={saving} onClick={() => void acceptAgreement()}>
                确认签署电子协议
              </Button>
            </div>
          )}
          {agreementAction === 'legacy_upload' && (
            <div className="space-y-3 rounded border border-solid border-gray-200 p-4">
              <Alert type="warning" showIcon message="这是历史文件签署协议，请使用当前协议编号和版本的完整文本完成签署并上传。" />
              <Space wrap>
                <FileUpload accept="image/*,application/pdf" disabled={saving} onUploaded={(asset) => setMerchantSignedAssetId(asset.id)} />
                {merchantSignedAssetId && <Tag color="green">商家签署文件已上传</Tag>}
              </Space>
              <div><Checkbox checked={agreementConfirmed} onChange={(event) => setAgreementConfirmed(event.target.checked)}>我确认上传文件对应上述协议编号、版本及完整协议文本</Checkbox></div>
              <Button type="primary" loading={saving} onClick={() => void submitSignedAgreement()}>提交商家签署文件</Button>
            </div>
          )}
        </div>
      )}

      <Modal title="编辑店铺信息" open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => void saveEdit()} confirmLoading={saving}>
        <Form form={form} layout="vertical" initialValues={shop ?? undefined}>
          <Form.Item name="name" label="店铺名称" rules={[{ required: true }, { max: 100 }]}><Input /></Form.Item>
          <Form.Item name="description" label="店铺简介" rules={[{ max: 500 }]}><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <Modal
        title="双方签署协议"
        open={signedAgreementPreview != null}
        footer={<Button type="primary" onClick={downloadSignedAgreement}>下载协议文件</Button>}
        onCancel={closeSignedAgreementPreview}
        width={720}
      >
        {signedAgreementPreview?.contentType === 'application/pdf'
          ? <iframe src={signedAgreementPreview.url} title="双方签署协议" style={{ width: '100%', height: '70vh', border: 0 }} />
          : signedAgreementPreview && <Image src={signedAgreementPreview.url} alt="双方签署协议" style={{ width: '100%' }} />}
      </Modal>
    </div>
  )
}
