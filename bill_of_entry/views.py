# Create your views here.
from django.views.generic import DetailView
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from . import forms, tables, filters
from . import models as bill_of_entry


class BillOfEntryView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = bill_of_entry.BillOfEntryModel
    table_class = tables.BillOfEntryTable
    filter_class = filters.BillOfEntryFilter
    page_head = 'Item List'


class BillOfEntryCreateView(CreateWithInlinesView):
    template_name = 'core/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm
    inlines = []

    # def form_valid(self, form):
    #     if not form.instance.created_by:
    #         form.instance.created_by = self.request.user
    #         form.instance.created_on = datetime.datetime.now()
    #     form.instance.modified_by = self.request.user
    #     form.instance.modified_on = datetime.datetime.now()
    #     return super().form_valid(form)


class BillOfEntryDetailView(DetailView):
    template_name = 'bill_of_entry/detail.html'
    model = bill_of_entry.BillOfEntryModel


class BillOfEntryLicenseImportItemInline(InlineFormSetFactory):
    model = bill_of_entry.RowDetails
    form_class = forms.ImportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class BillOfEntryUpdateView(UpdateWithInlinesView):
    template_name = 'core/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm
    inlines = [BillOfEntryLicenseImportItemInline,]

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        return super(BillOfEntryUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        object = self.model.objects.get(id=self.kwargs.get('pk'))
        return object

    def get_inlines(self):
        allotment = self.object.allotment
        if allotment:
            if allotment.allotment_details.all().exists():
                for allotment_item in allotment.allotment_details.all():
                    row, bool = RowDetails.objects.get_or_create(bill_of_entry=self.object,sr_number=allotment_item.item)
                    row.cif_inr = allotment_item.cif_inr
                    row.cif_fc = allotment_item.cif_fc
                    row.qty = allotment_item.qty
                    row.save()
                    allotment_item.is_boe = True
                    allotment_item.save()
        self.inlines = [BillOfEntryLicenseImportItemInline, ]
        return super(BillOfEntryUpdateView, self).get_inlines()


import json

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from license.models import RowDetails
from bill_of_entry.scripts.boe import fetch_cookies, fetch_captcha, fetch_data_to_model

from . import forms

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


# Create your views here.

class BillOfEntryFetchView(FormView):
    template_name = 'bill_of_entry/fetch.html'
    form_class = forms.BillOfEntryCaptcha

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryFetchView, self).get_context_data(**kwargs)
        cookies, csrftoken = fetch_cookies()
        context['captcha_url'] = fetch_captcha(cookies)
        import json
        context['fetch_cookies'] = json.dumps(cookies)
        context['csrftoken'] = csrftoken
        data = self.kwargs.get('data')
        context['remain_count'] = bill_of_entry.BillOfEntryModel.objects.filter(is_fetch=False).order_by('bill_of_entry_date', 'id').count()
        context['remain_captcha'] = context['remain_count'] / 3
        return context

    def post(self, request, *args, **kwargs):
        captcha = self.request.POST.get('captcha')
        cookies = json.loads(self.request.POST.get('cookies'))
        csrftoken = self.request.POST.get('csrftoken')
        data_dict = {
            'INBLJ6': 'AGRA ICD (INBLJ6)',
            'INAMD4': 'AHEMDABAD AIR ACC (INAMD4)',
            'INSBI6': 'AHEMDABAD ICD (INSBI6)',
            'INALA1': 'ALANG SEA (INALA1)',
            'INAPL6': 'ALBRATOS CFS PVT. LTD. ICD (INAPL6)',
            'INAMG6': 'AMINGAON ICD (INAMG6)',
            'INATQ4': 'AMRITSAR ACC (INATQ4)',
            'INASR2': 'AMRITSAR RAIL CARGO (INASR2)',
            'INAKV6': 'ANKALESHWAR ICD (INAKV6)',
            'INAJJ6': 'ARAKKANOM ICD (INAJJ6)',
            'INATRB': 'ATTARI ROAD (INATRB)',
            'INAZK1': 'AZHIKKAL PORT (INAZK1)',
            'INBDI6': 'BADDI ICD (INBDI6)',
            'INBGUB': 'BAIRGANIA (INBGUB)',
            'INBLE6': 'BALASORE Concor ICD (INBLE6)',
            'INBVC6': 'BALLABGARH CONCOR ICD (INBVC6)',
            'INFBD6': 'BALLABGARH ICD (INFBD6)',
            'INBSAB': ' BANBASA LCS (INBSAB)',
            'INBLR4': 'BANGALORE ACC (INBLR4)',
            'INWFD6': 'BANGALORE ICD (INWFD6)',
            'INBKT1': 'BANKOT PORT (INBKT1)',
            'INBAW6': 'BAWAL ICD (INBAW6)',
            'INBED1': 'BEDI PORT SEA (INBED1)',
            'INBNYB': 'BEHRNI LCS (INBNYB)',
            'INBEY1': 'BEYPORE PORT (INBEY1)',
            'INGRW6': 'BHAMBOLI ICD (INGRW6)',
            'INBHU1': 'BHAVNAGAR SEA (INBHU1)',
            'INBHL6': 'BHILWARA ICD (INBHL6)',
            'INBWD6': 'BHIWADI ICD (INBWD6)',
            'INBNRB': 'BHIMNAGAR (INBNRB)',
            'INBTMB': 'BHITAMORE (INBTMB)',
            'INBBI4': 'BHUBANESWAR AIR CARGO (INBBI4)',
            'INBSL6': 'BHUSAWAL ICD (INBSL6)',
            'INDLOB': 'BIRPARA (INDLOB)',
            'INBOK6': 'BORKHEDI ICD (INBOK6)',
            'INNGB6': 'BUTIBORI ICD (INNGB6)',
            'INCCJ4': 'CALICUT ACC (INCCJ4)',
            'INNSK6': 'CFS NASIK ICD (INNSK6)',
            'INCPC6': 'CHAKERI KANPUR ICD (INCPC6)',
            'INCHMB': 'CHAMURCHI (INCHMB)',
            'INCBDB': 'CHANGRABANDHA (INCBDB)',
            'INCPR6': 'CHAWAPAYAL ICD (INCPR6)',
            'INASR6': 'CHEHERTA ICD (INASR6)',
            'INMAA4': 'CHENNAI AIR CARGO ACC (INMAA4)',
            'INMAA1': 'CHENNAI SEA (INMAA1)',
            'INCHE6': 'CHETTIPALAYM ICD (INCHE6)',
            'INCCH6': 'CHINCHWAD PUNE ICD (INCCH6)',
            'INCPL6': 'CMA CGM LOGISTICS PARK ICD (INCPL6)',
            'INCOK4': 'COCHIN AIR CARGO ACC (INCOK4)',
            'INCOK1': 'COCHIN SEA (INCOK1)',
            'INCJB4': 'COIMBATORE ACC (INCJB4)',
            'INBGK6': 'CONCOR JODHPUR ICD (INBGK6)',
            'INCDL1': 'CUDDALORE PORT (INCDL1)',
            'INDHP1': 'DABHOL PORT (INDHP1)',
            'INDER6': 'DADRI ICD (INDER6)',
            'INDAH1': 'DAHEJ PORT SEA (INDAH1)',
            'INDRGB': 'DARRANGA LCS (INDRGB)',
            'INBRC6': 'DASHRATH VADODRA ICD (INBRC6)',
            'INDEL4': 'DELHI AIR CARGO ACC (INDEL4)',
            'INDHU1': 'DHAHANU PORT (INDHU1)',
            'INDMA1': 'DHAMRA PORT SEA (INDMA1)',
            'INDHA6': 'DHANNAD ICD (INDHA6)',
            'INDLAB': 'DHARCHULA LCS (INDLAB)',
            'INDMT1': 'DHARMATAR PORT MUMBAI (INDMT1)',
            'INDIG6': 'DIGHI ICD (INDIG6)',
            'INDIG1': 'DIGHI PORT (INDIG1)',
            'INDUR6': 'DURGAPUR ICD (INDUR6)',
            'INFBRB': 'FULBARI (INFBRB)',
            'INGGV1': 'GANGAVARAM PORT SEA (INGGV1)',
            'INGALB': 'GALGALIA (INGALB)',
            'INGHR6': 'GARI HARSARU ICD (INGHR6)',
            'INPNY6': 'GFPULICHAPALLAM ICD (INPNY6)',
            'INGOI4': 'GOA ACC (INGOI4)',
            'INMRM1': 'GOA PORT SEA (INMRM1)',
            'INGPR1': 'GOPALPUR PORT (INGPR1)',
            'INSGF6': 'GRFL SAHNEWAL LUDHIANA ICD (INSGF6)',
            'INGAU4': 'GUWAHATI AIR CARGO (INGAU4)',
            'INHZA1': 'HAZIRA PORT SURAT (INHZA1)',
            'INHIR6': 'HIRA BORUSE SURAT ICD (INHIR6)',
            'INHSU6': 'HOSUR ICD (INHSU6)',
            'INHYD4': 'HYDERABAD ACC (INHYD4)',
            'INSNF6': 'HYDERABAD ICD (INSNF6)',
            'INLDH6': 'ICD CONCOR DHANDARI KALAN LUDHIANA (INLDH6)',
            'INHAS6': 'ICD HASSAN (INHAS6)',
            'INPRK6': 'ICD POWARKHEDA (INPRK6)',
            'INIDR4': 'INDORE ACC (INIDR4)',
            'INIGU6': 'IRUGUR ICD (INIGU6)',
            'INILP6': 'IRUNGATTUKOTTAI ICD (INILP6)',
            'INJGD1': 'JAIGARH PORT MAHARASHTRA (INJGD1)',
            'INJAI4': 'JAIPUR ACC (INJAI4)',
            'INJAI6': 'JAIPUR ICD (INJAI6)',
            'INJAK1': 'JAKHAU PORT (INJAK1)',
            'INJUC6': 'JALANDHAR ICD (INJUC6)',
            'INJGA4': 'JAMNAGAR AIR CARGO (INJGA4)',
            'INJNR4': 'JANORI ACC (INJNR4)',
            'INJNR6': 'JANORI ICD (INJNR6)',
            'INJAYB': 'JAYANAGAR (INJAYB)',
            'INDWN6': 'JATTIPUR ICD (INDWN6)',
            'INJHOB': 'JHULAGHAT LCS (INJHOB)',
            'INJBNB': 'JOGBANI (INJBNB)',
            'INKNU6': 'JRY KANPUR ICD (INKNU6)',
            'INKAK1': 'KAKINADA SEA (INKAK1)',
            'INSKD6': 'KALINGANAGAR ICD (INSKD6)',
            'INENR1': 'KAMARAJAR PORT (INENR1)',
            'INPBLB': 'KAMARDWISA LCS (INPBLB)',
            'INKKU6': 'KANAKPURA ICD (INKKU6)',
            'INIXY1': 'KANDLA SEA (INIXY1)',
            'INSNI6': 'KANECH SAHNEWAL ICD (INSNI6)',
            'INKRK1': 'KARAIKAL SEA PORT (INKRK1)',
            'INKAR6': 'KARUR ICD (INKAR6)',
            'INKRW1': 'KARWAR PORT (INKRW1)',
            'INHPI6': 'KASHIPUR ICD (INHPI6)',
            'INMDU6': 'KERN ICD MADURAI (INMDU6)',
            'INKNLB': 'KUNAULI (INKNLB)',
            'INKAT1': 'KATTUPALLI PORT SEA (INKAT1)',
            'INKSH1': 'KELSHI PORT (INKSH1)',
            'INCML6': 'KHATUWAS ICD (INCML6)',
            'INKHD6': 'KHEDA ICD (INKHD6)',
            'INAIK6': 'KHURJA ICD (INAIK6)',
            'INQRP6': 'KILARAIPUR ADANI ICD (INQRP6)',
            'INKDN1': 'KODINAR PORT (INKDN1)',
            'INCCU4': 'KOLKATA ACC (INCCU4)',
            'INCCU1': 'KOLKATA SEA (INCCU1)',
            'INKUK1': 'KOLLAM PORT SEA (INKUK1)',
            'INKTT6': 'KOTA ICD (INKTT6)',
            'INKYM6': 'KOTTAYAM ICD (INKYM6)',
            'INKBC6': 'KRIBHCO SURAT ICD (INKBC6)',
            'INKRI1': 'KRISHNAPATNAM PORT SEA (INKRI1)',
            'INJIGB': 'LCS JAIGAON (INJIGB)',
            'INNGRB ': 'LCS Nepalgunj Road (INNGRB )',
            'INNTVB': 'LCS Thoothibari (INNTVB)',
            'INCRXB': 'LOKSAN LCS (INCRXB)',
            'INLON6': 'LONI ICD (INLON6)',
            'INLKQB': 'LAUKAHA (INLKQB)',
            'INLKO4': 'LUCKNOW AIR CARGO (INLKO4)',
            'INLOK4': 'LUCKNOW AIR CARGO (INLOK4)',
            'INMBS6': 'MADHOSINGH ICD (INMBS6)',
            'INIXM4': 'MADURAI AIR CARGO (INIXM4)',
            'INMDA1': 'MAGDALA PORT SEA (INMDA1)',
            'INMPR6': 'MALANPUR ICD (INMPR6)',
            'INMWA6': 'MALIWADA ICD (INMWA6)',
            'INMDD6': 'MANDIDEEP ICD (INMDD6)',
            'INIXE4': 'MANGALORE AIR CARGO (INIXE4)',
            'INNML1': 'MANGALORE SEA (INNML1)',
            'INGNR6': 'MARRIPALAM ICD (INGNR6)',
            'INMUZ6': 'MODINAGAR ICD (INMUZ6)',
            'INMUL6': 'MULUND ICD (INMUL6)',
            'INBOM1': 'MUMBAI CUSTOM HOUSE SEA (INBOM1)',
            'INMUN1': 'MUNDRA SEA (INMUN1)',
            'INNPT1': 'NAGAPATTINAM CUSTOM HOUSE SEA (INNPT1)',
            'INNAG4': 'NAGPUR AIR CARGO (INNAG4)',
            'INNGP6': 'NAGPUR ICD (INNGP6)',
            'INNAV1': 'NAVLAKHI PORT (INNAV1)',
            'INNSA1': 'NHAVA SHEVA SEA (INNSA1)',
            'INOKH1': 'OKHA PORT (INOKH1)',
            'INIXE1': 'OLD MANGALORE PORT (INIXE1)',
            'INOMU1': 'OLD MUNDRA PORT (INOMU1)',
            'INMBD6': 'PAKWARA MORADABAD ICD (INMBD6)',
            'INPKR6': 'PALI ICD REWARI (INPKR6)',
            'INPWL6': 'PALWAL ICD (INPWL6)',
            'INPAN1': 'PANAJI PORT (INPAN1)',
            'INPNP6': 'PANIPAT ICD (INPNP6)',
            'INPNTB': 'PANITANKI-NAXALBARI (INPNTB)',
            'INPNK6': 'PANKI ICD (INPNK6)',
            'INHDD6': 'PANTNAGAR ICD (INHDD6)',
            'INPRT1': 'PARADEEP PORT SEA (INPRT1)',
            'INPTL6': 'PATLI ICD (INPTL6)',
            'INPPG6': 'PATPARGANJ ICD (INPPG6)',
            'INDPC4': 'PCCCC BANDRA-KURLA COMPLEX (INDPC4)',
            'INPTPB': 'PETRAPOLE (INPTPB)',
            'INPMP6': 'PIMPRI ICD (INPMP6)',
            'INKJIB': 'PIPRAUN (INKJIB)',
            'INPAV1': 'PIPAVAV - VICTOR PORT GUJARAT SEA (INPAV1)',
            'ININD6': 'PITHAMPUR ICD (ININD6)',
            'INBFR6': 'PIYALA ICD (INBFR6)',
            'INPNY1': 'PONDICHERRY CUSTOM HOUSE SEA (INPNY1)',
            'INPBD1': 'PORBANDAR PORT (INPBD1)',
            'INSLL6': 'PORT SINGANALLUR ICD (INSLL6)',
            'INDDL6': 'PSWC DHANDARI KALAN LUDHIANA (INDDL6)',
            'INPNQ4': 'PUNE AIR CARGO (INPNQ4)',
            'INTUP6': 'RAAKIYAPALAYAM ICD (INTUP6)',
            'INRDP2': 'RADHIKAPUR RAILWAY STATION (INRDP2)',
            'INRAI6': 'RAIPUR ICD (INRAI6)',
            'INJUX6': 'RAJSICO BASNI JODNPUR ICD (INJUX6)',
            'INRNG2': 'RANAGHAT RAILWAY STATION NADIA (INRNG2)',
            'INRNR1': 'RANPAR PORT RATNAGIRI MAHARASHTRA (INRNR1)',
            'INRTM6': 'RATLAM ICD (INRTM6)',
            'INRXLB': 'RAXAUL (INRXLB)',
            'INRED1': 'REDI PORT (INRED1)',
            'INRVD1': 'REVDANDA PORT (INRVD1)',
            'INREA6': 'REWARI ICD (INREA6)',
            'INJKA6': 'SACHANA ICD (INJKA6)',
            'INSAC6': 'SACHIN ICD (INSAC6)',
            'INBOM4': 'SAHAR AIR CARGO ACC (INBOM4)',
            'INSAL1': 'SALAYA PORT GUJRAT (INSAL1)',
            'INSIK1': 'SIKKA PORT (INSIK1)',
            'INSNG2': 'SINGHABAD RAILWAY STATION MALDA (INSNG2)',
            'INSNBB': 'SONABARSA (INSNBB)',
            'INSNLB': 'SONAULI LCS (INSNLB)',
            'INBDM6': 'SONEPAT ICD (INBDM6)',
            'INSXR4': 'SRINAGAR AIR CARGO (INSXR4)',
            'INSTT6': 'STARTRACK TERMINAL ICD (INSTT6)',
            'INTLG6': 'TALEGAON PUNE ICD (INTLG6)',
            'INBNG6': 'TARAPUR ICD (INBNG6)',
            'INSAU6': 'THAR DRY PORT ICD/AHMEDABAD GUJARAT ICD (INSAU6)',
            'INTHA6': 'THAR DRY PORT JODHPUR ICD (INTHA6)',
            'INTMX6': 'THIMMAPUR ICD (INTMX6)',
            'INTCR6': 'THRISSUR ICD (INTCR6)',
            'INTDE6': 'THUDIALUR ICD (INTDE6)',
            'INTKNB': 'TIKONIA LCS (INTKNB)',
            'INTRZ4': 'TIRUCHIRAPALLI AIR CARGO (INTRZ4)',
            'INTVT6': 'TONDIAPET ICD (INTVT6)',
            'INTTP6': 'TRIDENT TERMINAL PVT. LTD. ICD (INTTP6)',
            'INTRV4': 'TRIVANDRUM ACC (INTRV4)',
            'INTKD6': 'TUGLAKABAD ICD (INTKD6)',
            'INSAJ6': 'TUMB ICD (INSAJ6)',
            'INTUN1': 'TUNA PORT (INTUN1)',
            'INTUT6': 'TUTICORIN ICD (INTUT6)',
            'INTUT1': 'TUTICORIN SEA (INTUT1)',
            'INVAD1': 'VADINAR PORT (INVAD1)',
            'INVPI6': 'VAPI ICD (INVPI6)',
            'INVNS4': 'VARANASI AIR CARGO (INVNS4)',
            'INTHO6': 'VEERAPANDI ICD (INTHO6)',
            'INMDG6': 'VERNA ICD (INMDG6)',
            'INVYD1': 'VIJAYDURG PORT (INVYD1)',
            'INVTZ4': 'VISHAKHAPATNAM AIR CARGO (INVTZ4)',
            'INVTZ1': 'VIZAG SEA (INVTZ1)',
            'INVZJ1': 'VIZHINJAM PORT (INVZJ1)',
            'INWAL6': 'WALUJ ICD (INWAL6)',
            'INCHJ6': 'WARDHA ICD (INCHJ6)',
        }
        status = True
        while status:
            status = fetch_data_to_model(cookies, csrftoken, data_dict, kwargs, captcha)
        if bill_of_entry.BillOfEntryModel.objects.filter(is_fetch=False).exclude(failed=5).exists():
            return HttpResponseRedirect(reverse('bill_of_entry'))
        else:
            return HttpResponseRedirect(reverse('bill_of_entry'))


