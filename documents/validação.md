openapi: 3.0.2

info:
  title: Adapter Geoawereness Provider
  description: TODO
  version: 0.0.1

tags:
  - name: adapter
    description: >-
      Endpoints this adapter exposes
  - name: geoawareness
    description: >-
      Endpoints provided by Geoawareness Provider and consumed by the adapter

components:
  schemas:
    #
    # ED-269 compliant GeoZone representation
    #
    UasZone:
      type: object
      description: >-
        An airspace of defined dimensions, above the land areas or territorial
        waters of a State, within which a particular restriction or condition
        for UAS flights applies.
      required:
        - identifier
        - country
        - type
        - restriction
        - zoneAuthority
        - geometry
      properties:
        identifier:
          anyOf:
            - $ref: '#/components/schemas/CodeZoneIdentifierType'
          description: >-
            A string of characters that uniquely identifies the UAS Zone within
            the State/Territory identified by the country attribute.
            
            Note - The UAS Zone is uniquely identified worldwide by the
            combination of the country and the identifier attributes
        country:
          anyOf:
            - $ref: '#/components/schemas/CodeCountryISOType'
          description: >-
            The State that has the authority to declare the zone.
            
            Note - There will be no Zone belonging to two States. Not necessary
            to code the information that two zones are "in neighboring States"
            or "related".
        zoneAuthority:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/Authority'
        name:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            A free text name by which the zone may be known by the public or by
            the UAS community.
        type:
          anyOf:
            - $ref: '#/components/schemas/CodeZoneType'
          description: >-
            An indication whether the Zone is provided with its common
            definition or with a customised definition, for a particular user.
        restriction:
          anyOf:
            - $ref: '#/components/schemas/CodeRestrictionType'
          description: >-
            An indication if flying in the zone is conditional, forbidden or
            unrestricted.
        restrictionConditions:
          type: array
          items:
            $ref: '#/components/schemas/ConditionExpressionType'
          description: >-
            An indication of the conditions under which the zone can be used
        region:
          type: integer
          format: int32
          minimum: 0
          maximum: 65535
          description: >-
            Where applicable, identifies a region inside a State where the UAS
            Zone is located.
            
            Note 1) identified with a digit between 0-65535 (16 bit),
            corresponding to a list of regions pre-defined for each State.
            
            Note 2) this attribute is intended to facilitate extracting sub-sets
            of data, for specific regions
        reason:
          items:
            $ref: '#/components/schemas/CodeZoneReasonType'
          description: >-
            A coded indication for the reason that led to the establishment of
            the zone.
          maxItems: 9
          type: array
        otherReasonInfo:
          type: string
          maxLength: 30
          description: >-
            A free text description of the reason that led to the establishment
            of the zone, when not covered by a pre-defined coded value.
        regulationExemption:
          anyOf:
            - $ref: '#/components/schemas/CodeYesNoType'
          description: >-
            This is an extension point. It allows adding additional attributes
            of national interest through this element.
        uSpaceClass:
          anyOf:
            - $ref: '#/components/schemas/CodeUSpaceClassType'
          description: >-
            A code that identifies the category or class of the zone applying a
            "USpace concept".
            
            Note: Two (draft) classifications exist, one from Eurocontrol and
            one from CORUS. Therefore, two instances of this attribute are
            expected, one from each sub-list. This might be later replaced with
            separate attributes and separate lists of values.
        message:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            A message to be displayed to the user of the zone, typically on the
            RPS for the Remote Pilot, to make him/her aware about specific
            information associated with the zone (typically when it is not only
            a restriction to fly in the zone, thus not only an alert or an
            automatic limitation, for example : “image capture prohibited in
            this zone”, “frequent strong winds in this zone”, “no landing or
            take-off in this zone”). This message is also used to indicate
            exemptions from regulation in a zone (see below). Several
            information can be grouped in a message, separated by a “/”.
        additionalProperties:
          type: object
          default:
          description: >-
            Indicates that exemptions from the national or European regulations
            are allowed in the UAS Zone, that will be detailed via the "message"
            property.
        applicability:
          type: array
          items:
            anyOf:
              - $ref: '#/components/schemas/TimePeriod'
        geometry:
          type: array
          items:
            anyOf:
              - $ref: '#/components/schemas/AirspaceVolume'
          minItems: 1
    TimePeriod:
      type: object
      description: >-
        Defines the applicability dates and times of the zone, including 
        its eventual usage permissions/restrictions.
      required:
        - permanent
      properties:
        permanent:
          description: >-
            An indication that the area is permanent if Yes. Permanent 'Yes' means:
            always active, no start nor end date.
            Permanent 'No' means: consider the start and end date provided just after.
          anyOf:
            - $ref: '#/components/schemas/CodeYesNoType'
        startDateTime:
          description: >-
            The date and time when the area starts to exist.
          anyOf:
            - $ref: '#/components/schemas/DateTimeType'
        endDateTime:
          description: >-
            The date and time when the area ceases to exist.
          anyOf:
            - $ref: '#/components/schemas/DateTimeType'
        schedule:
          type: array
          items:
            anyOf:
              - $ref: '#/components/schemas/DailyPeriod'
    AirspaceVolume:
      type: object
      description: >-
        The definition of the airspace volume comprised by the zone, in the form of:
        
        - either a single cylinder with a horizontal projection and vertical limits;
        
        - or a vertical stack of cylinders, each with its own horizontal projection and
        with distinct vertical limits, corresponding to an "inverted cone" geometry for the UAS.
        
        NOTE: 'Cylinder' does not mean only a circular horizontal projection. It can be any
        polygonal shape.
      required:
        - uomDimensions
        - horizontalProjection
      properties:
        uomDimensions:
          anyOf:
            - $ref: '#/components/schemas/UomDistance'
        lowerLimit:
          type: integer
          description: >-
            The lowest level included in the Zone. If not specified, it means that the
            zone starts from surface (ground).
            
            Note: The resolution of the value shall be of at least 1m.
        lowerVerticalReference:
          anyOf:
            - $ref: '#/components/schemas/CodeVerticalReferenceType'
          description: >-
            The vertical reference system used for expressing the lower limit.
        upperLimit:
          type: integer
          description: >-
            The highest level included in the Zone. If not specified, it means that te zone extends
            to any possible level (unlimited).
            
            Note: The resolution of the value shall be of at least 1m.
        upperVerticalReference:
          anyOf:
            - $ref: '#/components/schemas/CodeVerticalReferenceType'
          description: >-
            The vertical reference system used for expressing the upper limit.
        horizontalProjection:
          anyOf:
            - $ref: '#/components/schemas/GeoShapeType'
          description: >-
            The shape of the area in a projection at the surface of the Earth considered
            as the WGS-84 ellipsoid.
            
            Note: The resolution of the latitude/longitude coordinates should be at least 1m.
    DailyPeriod:
      type: object
      description: >-
        Specifies a daily applicability schedule of the zone and its eventual
        permission/restrictions, within the time when the area exists according to the
        TimePeriod information.
      properties:
        day:
          type: array
          items:
            anyOf:
              - $ref: '#/components/schemas/CodeWeekDayType'
          description: >-
            The day of the week
          minItems: 1
          maxItems: 7
        startTime:
          anyOf:
            - $ref: '#/components/schemas/TimeType'
          description: >-
            The daily start time
        endTime:
          anyOf:
            - $ref: '#/components/schemas/TimeType'
          description: >-
            The daily end time
    UomDistance:
      type: string
      description: >-
        A list of units of measurement used for distances
        
        M - Meters
        FT - Feet
      enum:
        - M
        - FT
    GeoShapeType:
      anyOf:
        - $ref: '#/components/schemas/PolygonType'
    PolygonType:
      type: object
      description: >-
        Type for the description of the airspaceVolume projection onto the Earth's surface.
        This type is a specialization of a geoJSON Polygon. The coordinates must be expressed
        as an array of [lon, lat] arrays using the Coordinate Reference System
        urn:ogc:def:crs:OGC::CRS84 as per geoJSON Specification. See: https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.6
      required:
        - type
        - coordinates
      properties:
        type:
          type: string
          enum:
            - Polygon
        coordinates:
          type: array
          items:
            type: array
            minItems: 4
            items:
              type: array
              minItems: 2
              maxItems: 2
              items:
                type: number


    DateTimeType:
      type: string
      description: >-
        RFC3339-formatted time/date string.  The time zone must be 'Z'.
      format: date-time
      example: '1985-04-12T23:20:50.52Z'
    CodeWeekDayType:
      type: string
      description: >-
        A coded value indicating a day of the week
        
        MON - Monday
        TUE - Tuesday
        WED - Wednesday
        THU - Thursday
        FRI - Friday
        SAT - Saturday
        SUN - Sunday
        ANY - Any day of the week
      enum:
        - MON
        - TUE
        - WED
        - THU
        - FRI
        - SAT
        - SUN
        - ANY
    CodeVerticalReferenceType:
      type: string
      description: >-
        A coded value that indicates a vertical reference system
        
        AGL - Height above ground/surface level
        AMSL - Altitude above Mean Sea Level
      enum:
        - AGL
        - AMSL
    TimeType:
      type: string
      format: ISO 8601
      description: >-
        A time instant type in the form of hh:mmS
        
        Note: the date and time format shall follow the ISO 8601 standard, with 'S' indicating
        the time zone
      example: 23:20Z

    CodeZoneIdentifierType:
      type: string
      maxLength: 7
      description: >-
        a string of maximum 7 characters that uniquely identifies the area
        within a geographical scope.
        
        NOTE (1): This shall not include the country identifier, which is a
        separate attribute of the UAS Zone.
        
        NOTE (2): The length of this data type is limited to 7 characters for
        compatibility with ARINC 424 and AIXM, where an airspace designator may
        have maximum 10 characters. The 10 characters are the result of
        concatenating the UAS Zone attributes for country and identifier.
    CodeCountryISOType:
      type: string
      minLength: 3
      maxLength: 3
      description: >-
        A 3 letter identifier of a country or territory using the ISO 3166-1
        alpha-3 standard.
        
        NOTE: >-
           The ISO 3-letter country codes come with the following advantages:
              - allow to distinguish between remote territories and mainland
              - are unique, unlike the ICAO Country codes where the same State
                could have two or more codes
              - are also used in military standards, such as NATO STANAG 1059
                INT, which come with well document additions that might be also
                useful for UAS areas.
    CodeZoneType:
      type: string
      description: >-
        A coded list of values which allows indicating that the definition of a
        UAS Zone is specifically customised for a particular UAS or operator.
      enum:
        - COMMON
        - CUSTOMIZED
    ConditionExpressionType:
      type: string
      maxLength: 10000
      description: >-
        A coded expression that provides information about what is authorised /
        forbidden in a zone that has conditional access.
        
        By difference with the “Message” field per zone, this coded expression
        is made to be interopreted by the UAS while the “Message” is to
        interpreted by the remote pilot.
        
        NOTE: the maximum field length is 10 000 characters.
        
        ---------------------- Condition definition language ---------------- •
        A list of relevant characteristics (CHARTYPE) has first to be
        established per state, and their finite list of acceptable values
        (CHARVAL)
        
        • Each chartype and charval fields are defined by a limited set of
        characters
        
        • A public document shall give the definitions of each, and provide the
        reference to legal or technical characteristics implied
        
        • The Geozone editor per state can use these characteristics, with the
        dedicated condition language defined below, to define exact conditions
        per zone
        
        • Each UAS Geofencing function shall be loaded with the corresponding
        chararacteristic status of the UAS for the intended flight, so as to be
        able to apply the conditions , either to generate alerts or to limit the
        flight
        
        • If the value of a given characteristic of the condition equation is
        not defined in the UAS, the UAS Geofencing function should inform the
        pilot in Geoawareness alerting or consider that the zone is forbidden,
        by default in automatic Geofencing.
        
        A conditional expression shall be of the following type:
        
        • The UAS is PERMITTED XOR PROHIBITED (exclusive choice) to fly in this
        zone at this time IF (Characteristic1) CHARTYPE1 = (Value1) CHARVAL1 AND
        
        CHARTYPE 2 = CHARVAL 2 AND ... AND End IF
        
        OR (...)
        
        ...
        
        End OR
        
        • Only the fields in bold need to be edited in the character string,
        separated by”/”. Others are implicit.
        
        Examples of CHARTYPE and CHARVALUE:
        
        • CHARTYPE: operator type; Acceptable CHARVAL values:
        Military/Police/Firefighting
        
        • CHARTYPE: Operator ID (registration number); Acceptable CHARVAL
        values: as per registration format
        
        • CHARTYPE: Operation type: A1 as per EASA Open Types or S1 (National
        standard Scenario 1), STS01 (EASA Specific standard scenario) or ...
        
        • CHARTYPE: UTM operation type: Planned/Unplanned,
        
        • CHARTYPE: passengers on board: yes /no Note that it is possible in
        each national catalog of chartype and charval items, to define complex
        categories of operation/drone /equipment. Example: In nation A, we may
        have a type “drone level” with values Low, Medium, High. Each level
        corresponds to a defined set of required UAS performance/operation
        features/ operator qualification etc. This avoids to code a complex
        combination in the geozone database. This conditional expression can
        also be used to code a prohibition of image capture in a zone.
        
        Example: PERMITTED/IMAGE CAPTURE=NO/NOISE
        
          CLASS=A/OR/OPERATOR=POLICE
        
        Meaning: >-
           the fight is permitted in this zone at that time if No image is
        captured (removed or deactivated) and if noise class = class A
        (following a known classification) or if the UAS operator is the Police
    CodeRestrictionType:
      type: string
      description: >-
        An indication if flying in the zone is conditional, forbidden or
        unrestricted.
      enum:
        - PROHIBITED
        - REQ_AUTHORISATION
        - CONDITIONAL
        - NO_RESTRICTION
    CodeZoneReasonType:
      type: string
      description: >-
        A coded indication of a reason that justifies the existence of an UAS
        Zone
      enum:
        - AIR_TRAFFIC
        - SENSITIVE
        - PRIVACY
        - POPULATION
        - NATURE
        - NOISE
        - FOREIGN_TERRITORY
        - EMERGENCY
        - OTHER
    CodeUSpaceClassType:
      type: string
      maxLength: 100
      description: >-
        A coded identifier for a category or class of the zone applying a
        "USpace concept".
        
        NOTE: >-
           In the current model version, there is no specific list of values.
        For example, the “X”, “Y”, “Z” types of zones as per SESAR JU Corus
        project on USpace concept of operation could be used in a future
        version. Until a precise list of values is defined, this data type will
        be considered as string of characters of maximum 100 characters.
    CodeYesNoType:
      type: string
      description: >-
        A coded value that indicates a choice between a positive (yes) or a
        negative (no) applicability.
      enum:
        - "YES"
        - "NO"
    Authority:
      type: object
      description: >-
        A relevant authority that is in charge for authorising, being notified
        or providing information for UAS operations in the UAS zone.
        
        Rule: >-
           at least one of the following shall be specified - siteURL, email,
        phone.
      properties:
        name:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: The official name of a public or private authority
        service:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            The name of a specific department or service within the organisation
        contact_name:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            The name or role of a specific person that needs to be contacted
            within the organisation
        site_url:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            The URL of the public internet site through which the organisation
            may be contacted
            
            Note: in the data coding format, this might be further constrained
            in order to ensure a valid URL format.
        email:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            The e-mail address by which the organisation may be contacted.
            
            Note: in the data coding format, this might be further constrained
            in order to ensure a valid e-mail format.
        phone:
          anyOf:
            - $ref: '#/components/schemas/TextShortType'
          description: >-
            A phone number at which the organisation may be contacted
        purpose:
          anyOf:
            - $ref: '#/components/schemas/CodeAuthorityRole'
          description: The role of the Authority in relation with the zone.
        interval_before:
          type: string
          format: duration
          description: >-
            The minimal time interval required between notification or
            authorization request and starting to operate in the zone, in the
            format PnnDTnnHnnM (ISO 8601).
    CodeAuthorityRole:
      type: string
      description: >-
        A coded list of values indicating the role that an authority has in
        relation with the UAS zone.
      enum:
        - AUTHORIZATION
        - NOTIFICATION
        - INFORMATION
    TextShortType:
      type: string
      maxLength: 200
      description: A free text with a maximum length of 200 characters
    FetchRestrictionsRequest:
      type: object
      properties:
        geometry:
          anyOf:
            - $ref: '#/components/schemas/AirspaceVolume'
    FetchRestrictionsResponse:
      type: array
      items:
        anyOf:
          - $ref: '#/components/schemas/UasZone'
    ErrorResponse:
      description: >-
        Human-readable string returned when an error occurs
        - DSS transaction.
      type: object
      required:
        - message
      properties:
        message:
          description: >-
            Human-readable message indicating what error occurred and/or why.
          type: string
          example: The error occurred because [...]
paths:
  /adapter/v1/restrictions:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/FetchRestrictionsRequest'
      summary: Endpoint to fetch all constraints in specific geometry
      tags:
        - adapter
      responses:
        '200':
          description: Fetch succeeded
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/FetchRestrictionsResponse'

  /geoawareness/v1/constraint:
    put:
      summary: Endpoint to create a constraint
      tags:
        - geoawareness
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UasZone'
      responses:
        '200':
          description: Added successfully
        '400':
          description: Bad request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
  /geoawareness/v1/constraint/{entityid}:
    parameters:
      - name: entityid
        description: ED269 Identifier
        in: path
        schema:
          type: string
        required: true
    put:
      summary: Endpoint to update a constraint
      tags:
        - geoawareness
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UasZone'
      responses:
        '200':
          description: Updated successfully
        '400':
          description: Bad request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
    delete:
      summary: Endpoint to delete a constraint
      tags:
        - geoawareness
      responses:
        '204':
          description: Deleted successfully
        '500':
          description: Internal Server Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'