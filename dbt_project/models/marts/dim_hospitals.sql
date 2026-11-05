-- The one dimension every fact joins to. Attributes of a hospital only:
-- anything that is a measurement lives in a fact table.
select
    facility_id,
    -- CMS publishes names in ALL CAPS, which reads as shouting across every
    -- visual. initcap() fixes the bulk of it but flattens genuine acronyms,
    -- so the frequent ones measured in the data are restored afterwards:
    -- VA (134 names), LLC (87), HCA (52), plus UMass.
    --
    -- This is presentation logic, so it lives in the mart rather than in
    -- staging, which stays a pure rename-and-recast layer. The raw name is
    -- kept alongside it -- a title-cased name is for reading, not for
    -- matching against another system.
    {{ display_name('hospital_name') }}               as hospital_name,
    hospital_name                                    as hospital_name_raw,
    address,
    city,
    state,
    zip_code,
    county,
    hospital_type,
    hospital_ownership,
    emergency_services,
    birthing_friendly,
    overall_rating,

    -- CMS reports on US territories as well as states. Their hospitals are
    -- real and belong in national aggregates, but they span roughly 160
    -- degrees of longitude, so any map that includes them auto-zooms to the
    -- whole globe and the continental US becomes unreadable.
    --
    -- Making this an attribute lets a visual filter on a column rather than
    -- hardcoding a list of codes to exclude, and keeps the territories
    -- available when a national figure is what is wanted.
    case
        when state = 'DC'                            then 'District'
        when state in ('AS', 'GU', 'MP', 'PR', 'VI') then 'Territory'
        else 'State'
    end as region_type,

    load_date
from {{ ref('stg_hospitals') }}
