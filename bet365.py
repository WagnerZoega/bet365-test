from time import sleep
import datetime
import io
import os.path
import pygame
from typing import List, Tuple, Dict, Union
from selenium.webdriver.remote.webelement import WebElement
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException, ElementClickInterceptedException, ElementNotInteractableException

#TODO e1 indiviadually
#TODO QA e2345

WebElements = List[WebElement]
TeamDict = Dict[str, Union[int, str]]

#HELPER FUNCTIONS
def init_params() -> Tuple[TeamDict, int, int, int, str, str, List[str]]:
    """uses data in 'dados.txt' to initialize parameters
    returns STRATEGIES, STAKE, RISK_UPPER, RISK_LOWER, PATH, PARAMS_LEAGUES"""
    with io.open('dados.txt', 'r', encoding='utf-8') as params:
        params_strategies = {}
        PARAMS_LEAGUES, STAKE, PATH, RISK_UPPER, RISK_LOWER, j = [], 0, '', 0, 0, 0
        global_vars = [STAKE, RISK_UPPER, RISK_LOWER, PATH, PARAMS_LEAGUES]
        for i, line in enumerate(params.readlines()):
            line = line.strip(" \n")
            if i <= 24:
                if '*' in line:
                    if i == 0:
                        pass
                    else:
                        params_strategies[strategy[:-1]] = params_strategy #dict of dicts
                    params_strategy = {} #dict 
                    strategy = line #key of params_strategies
                    params_strategy['name'] = strategy[:-1]
                
                else:
                    params_strategy[line.split(':')[0]] = float(line.split(':')[1])
                    if i == 24:
                        params_strategies[strategy[:-1]] = params_strategy

            else:
                if '$' in line:
                    j += 1
                    continue
                if j < 4:
                    global_vars[j-1] = float(line)/100 #stake, risk_upper, risk_lower
                elif j == 4:
                    global_vars[j-1] = str(line) #path
                else:
                    global_vars[4].append(line) #param_leagues
    
    params_strategies['e11'] = params_strategies['e1']
    return (params_strategies, global_vars[0], global_vars[1], global_vars[2], global_vars[3], global_vars[4])

STRATEGIES, STAKE, RISK_UPPER, RISK_LOWER, PATH, PARAMS_LEAGUES = init_params()
driver = webdriver.Chrome(executable_path=PATH)
driver.implicitly_wait(10)
REPORT_FREQ = datetime.timedelta(hours=1)cap = DesiredCapabilities().FIREFOX
cap["marionette"] = False
USERS, RISK_USERS = [], []
(WIDTH, HEIGTH) = (400, 400)
BG_COLOR = (255, 255, 255)
screen = pygame.display.set_mode((WIDTH, HEIGTH))
screen.fill(BG_COLOR)
pygame.display.flip()


class User(object):
    def __init__(self, username: str, password: str):
        self.username: str = username
        self.password: str = password
        self.pending_bets: List[List[str]] = []
        self.read_pending_bet()
        self.owned_init = 0 #this will be set on login 

    def read_pending_bet(self) -> None:
        """initialize self.last_report, reads {}_pending_bets.txt and appends bets in self.pending_bets
        if {}_pending_bets.txt doesn't exist creates it"""
        self.last_report = datetime.datetime.now()
        if not os.path.isfile(f'{self.username}_pending_bets.txt'):
            with io.open(f'{self.username}_pending_bets.txt', 'w', encoding='utf-8') as bets:
                bets.write('Team Names, ano, mes, dia, horario, estrategia, linha, appm, cg, rend, balan,  Betting Type$')
        
        else:
            with io.open(f'{self.username}_pending_bets.txt', 'r', encoding='utf-8') as bets:
                for bet in bets.readlines():
                    if bet.strip('\n')[-1] != '$':
                        temp = bet.strip('\n').lower().split(',')
                        self.pending_bets.append([item.strip(' ') for item in temp[:12]] + [[item.strip('\'[] ') for item in bet[12:].split(',')]])

    def write_pending_bet(self, mode: str, team: TeamDict = 0, strategy: str = 0, line: str = 0, when: datetime = 0) -> None:
        """this method is called everytime a bet is made.
        it writes bet's details in {}_pending_bets.txt and mutates self.pending_bets
        mode == 'bet' -> team, strategy, line and when are required, appends
        mode == 'report' -> None of that is required, overwrites {}_pending_bets.text"""
        look_report = {'e1': ['10:00'], 'e2': ['escanteios'], 'e3': ['escanteios'],
        'e4': ['escanteios', 'opções'], 'h1': ['handicap', 'asiático']}

        #there are 12 collumns in self.pending_bets    
        if mode == 'bet': #this appends 1 bet
            with io.open(f'{self.username}_pending_bets.txt', 'a+', encoding='utf-8') as bets:
                bet = f"{team['name']}, {when.year}, {when.month}, {when.day}, {when.isoformat(' ').split(' ')[1][:8]}, \
                    {strategy}, {line}, {team['appm']}, {team['cg']}, {team['rend']}, {team['balan']}, {look_report[strategy]}"
                bets.write("\n")
                bets.write(bet)
            self.pending_bets.append([item.strip(' ') for item in bet[:12].split(',')] + [[item.strip('\'[] ') for item in bet[12:].split(',')]])
        
        if mode == 'report': #this overwrites with all pending_bets
            with io.open(f'{self.username}_pending_bets.txt', 'w+', encoding='utf-8') as bets:
                bets.write('Team Names, ano, mes, dia, horario, estrategia, linha, appm, cg, rend, balan, Betting Type$')
                for bet in self.pending_bets:
                    text = ", ".join(bet[:12]).lower() + ", " + ", ".join(bet[12]).lower()
                    bets.write("\n"+text)

    def get_money(self) -> float:
        """returns how much is currently owned
        also sets self.owned_init the first time it places a bet""" 
        money = get_owned()
        try:
            assert type(self.owned_init) == float
        except AssertionError: #The first time one tries to make a bet this is evoked
            self.owned_init = money
        finally:
            return money     

    def write_report(self) -> None:
        """writes bets in self.pending_bets found in "resolvidas" tab in report.txt"""
        condition_dict = {'green': 'win', 'red': 'loss'}
        avoid_report = {'e2': ['asiático'], 'e4': ['asiático']}

        #makes report file if there's none
        if not os.path.isfile('report.txt'):
            with io.open('report.txt', 'w', encoding='utf-8') as report:
                report.write("ano, mes, dia, horário, estratégia, linha, appm, cg, rend, balan, resultado parcial, resultado, usuário$")

        #surfing to "minhas apostas resolvidas" page
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "hm-MainHeaderCentreWide_Link")))
        tabs = driver.find_elements_by_class_name("hm-MainHeaderCentreWide_Link")
        find_item('minhas apostas', tabs).click()
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "myb-MyBetsHeader_Button ")))
        categories = driver.find_elements_by_class_name("myb-MyBetsHeader_Button ")
        find_item('resolvidas', categories).click()
        
        outer_counter, inner_counter, already_reported, bets_iterator = 0, [], [], self.pending_bets.copy() #inner_counter counts green in e3/5
        bet_containers = driver.find_elements_by_class_name("myb-SettledBetItem") #bet container
        for pending_bet in bets_iterator: #for each pending bet, check all bets in "resolvidas" tab
            bet_containers = list(filter(lambda bet: bet not in already_reported, bet_containers))        
            for i, bet_container in enumerate(bet_containers):
                #opens collapsed tab
                if len(bet_container.text.split('\n')) == 3:
                    bet_container.click()
                    bet_container = driver.find_elements_by_class_name("myb-SettledBetItem")[i]

                team_name = bet_container.find_element_by_class_name("myb-BetParticipant_FixtureDescription ").text.lower() #name of teams
                bet_type = bet_container.find_element_by_class_name("myb-BetParticipant_MarketDescription").text.lower() #type of bet
                line_type = bet_container.find_element_by_class_name("myb-BetParticipant_ParticipantSpan ").text.lower()
                    
                if (pending_bet[0] in team_name.lower()) and (pending_bet[6] in line_type) and ([pending_bet[1] in bet_type.lower()]) and (any([avoid not in bet_type.lower() for avoid in avoid_report[pending_bet[4]]])):
                    outer_counter, inner_counter, already_reported = self.text_manager(bet_container, condition_dict, pending_bet, outer_counter, inner_counter, already_reported)

            outer_counter += 1

        self.last_report = datetime.datetime.now()
        self.write_pending_bet('report')

    def risk_management(self) -> bool:
        owned_current = get_owned()
        delta = (self.owned_init - owned_current)/self.owned_init
        if  delta > + RISK_UPPER:
            print('You gained too much today. Let\'s stop now.')
            return True
        if delta < - RISK_LOWER:
            print('You lost too much today. Let\'s stop now.')
            return True
        
        return False    

    def text_manager(self, bet_container: WebElement, condition_dict: Dict[str, str], pending_bet: List[str], outer_counter: int, inner_counter: List[str], already_reported: WebElements):
        """pending_bet is the bet (list) that is being written
        outer_counter keeps track (int) for self.pending_bets
        inner_counter keeps track (list) of results in the same strategy"""
        result = bet_container.find_element_by_class_name("myb-SettledBetItem_BetStateContainer ").text #result
        #defines res_partial
        if 'perdida' in result: #sets res_partial
            res_partial = 'red'
        elif 'retorno' in result:
            res_partial = 'green'

        #defines res_final, pending_bet[6] is strategy
        if pending_bet[6] != 'e3' and pending_bet[6] != 'e5':
            res_final = condition_dict[res_partial]

        #if there are more bets of this type and team in sequence
        elif (pending_bet[0] == self.pending_bets[outer_counter+1][0]) and (pending_bet[12] == self.pending_bets[outer_counter+1][12]):
            res_final = '-'
            inner_counter.append(res_partial)

        #if this is the last bet of this type in sequence
        else:
            inner_counter.append(res_partial)
            res_final = 'win' if inner_counter.count('green')/len(inner_counter) > 0.5 else 'loss'
            inner_counter = []

        with io.open('report.txt', 'a+', encoding='utf-8') as report:
            text = ", ".join(pending_bet[2:])
            text = f"{text}, {text}, {res_partial}, {res_final}, {self.username}"
            report.write('\n')
            report.write(text)
        self.pending_bets.remove(pending_bet)
        outer_counter -= 1
        already_reported.append(bet_container)
        return outer_counter, inner_counter, already_reported


def find_item(value: str, items: WebElements) -> WebElement:
    """helper function to find an element with a 'value' text in items"""
    for item in items:
        if value in item.text.lower():
            return item

def find_exact1(value: str, items: WebElements) -> WebElement:
    """helper function to find an element that matches == 'value' text first line in items"""
    for item in items:
        if value == item.text.split('\n')[0].lower():
            return item

def find_item_avoiding(avoiding: List[str], items: WebElements, **kwargs) -> Union[WebElement, bool]:
    """helper function to find an element skipping 'avoiding' values in 'items'
    avoiding: list of str + ["00:00", "45:00"]
    items: list of WebElements
    kwargs: set_params = default to what always avoid
    returns a WebElement"""
    if len(avoiding) == 0 and kwargs.get('mode') == 'match':
        avoiding.append('00:00')
        avoiding.append('45:00')
    for item in items:
        valid = True
        if any([avoid == item.text.split('\n')[0].lower() for avoid in avoiding]): #if it's true, than there's an avoid in text
            valid = False
        if valid:
            return item
    print('No item found.')
    return False          

def find_all_items(items: WebElements, value_list: List[str]=PARAMS_LEAGUES) -> WebElements:
    """helper function to find all elements with a 'value' text in items"""
    items_list = []
    for item in items:
        if any([True if word in item.text.lower() else False for word in value_list]):
           items_list.append(item)
    return items_list

def convert_time(time: str) -> int:
    """Expects a str 'minutes:seconds'
    returns the time in seconds"""
    minutes = int(time.split(":")[0])*60
    seconds = int(time.split(":")[1])
    return minutes + seconds

def get_owned(driver=driver) -> float:
    a = driver.find_elements_by_class_name("hm-MainHeaderMembersWide_ButtonWrapper ")[0].text
    real, cent = int("".join(a.split('\n')[0].strip('R$').split(',')[0].split('.'))), int(a.split('\n')[0].strip('R$').split(',')[1])
    return real + cent/100

def get_time() -> int: 
    return convert_time(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "ipe-SoccerHeaderLayout_ExtraData "))).text)

#PROGRAM FUNCTIONS
def init_accounts(credentials_file: str) -> Dict[str, str]:
    """credentials_file is the path to file with credentials in shape: username password
    Returns a dict with username: password"""
    users = {}
    with open(credentials_file, 'r') as file:
        for account in file.readlines():
            users[account.split(' ')[0]] = account.split(' ')[1].strip('\n')

    return users
 
def login(user: User) -> float:
    """Expects that there's no account logged in bet365
    Logs in with given username/password"""
    username, password = user.username, user.password
    driver.get('https://www.bet365.com/#/HO/')
    print('after get')
    login = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "hm-MainHeaderRHSLoggedOutWide_Login ")))
    print('before click')
    login.click()
    
    #enters username and password
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "lms-StandardLogin_Username "))).send_keys(username)
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "lms-StandardLogin_Password "))).send_keys(password)
    driver.find_element_by_class_name("lms-StandardLogin_LoginButtonText ").click()
    WebDriverWait(driver, 60).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "messageWindow")))
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID,"remindLater"))).click()
    driver.switch_to.default_content()

    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "hm-MainHeaderMembersWide_ButtonWrapper ")))
    user.owned_init = get_owned()
    try:
        driver.find_element_by_class_name("pm-PushTargetedMessageOverlay_CloseButton ").click()
    except NoSuchElementException:
        pass

def logout() -> None:
    """Expects to be in a page with user_info button""" 
    #user_info
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "hm-MainHeaderMembersWide_MembersMenuIcon "))).click()
    
    #Checks if logout is avaiable
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "um-MembersLinkRow "))) 
    logout = find_item('sair', driver.find_elements_by_class_name("um-MembersLinkRow "))
    logout.click()

def search_matches() -> Union[WebElement, None]:   
    """Doesn't expect to be in any specific page
    returns a list of matches to evaluate"""
    #navigating to soccer matches page
    print("Starting to look for matches")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".hm-MainHeaderLogoWide_Bet365LogoImage"))).click()
    sports = driver.find_elements_by_class_name("wn-PreMatchItem ")
    find_item('futebol', sports).click() #go to soccer page
    live = driver.find_elements_by_class_name("hm-MainHeaderCentreWide_Link")
    find_item('ao-vivo', live).click() #go to live games 
    WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.CLASS_NAME, "ip-ControlBar_BBarItem"))).click() #click on "Geral"
    
    #collecting matches elements
    all_leagues = driver.find_elements_by_class_name("ovm-Competition")
    leagues = find_all_items(all_leagues, PARAMS_LEAGUES)
    matches_unav, leagues_unav = [], []
    while len(leagues) != len(leagues_unav):
        try:
            current_league = find_item_avoiding(leagues_unav, leagues) #gets next non-visited league
            if not current_league:
                print(f'No matches left to search.')
                break #just exists this function if there's no league to explore
            leagues_unav.append(current_league.text.split('\n')[0].lower())
            league_matches = current_league.find_elements_by_class_name("ovm-FixtureDetailsTwoWay_Wrapper") #gets all matches of that league
            num_matches = len(league_matches)
            while True:
                try:
                    assert len(current_league.find_elements_by_class_name("ovm-FixtureDetailsTwoWay_Wrapper")) == num_matches #asserts no match started or ended
                    current_match = find_item_avoiding(matches_unav, league_matches, mode = 'match')
                    if not current_match:
                        break
                    matches_unav.append(current_match.text.split('\n')[0].lower())
                    yield current_match
                except (AssertionError, StaleElementReferenceException):
                    break
        except StaleElementReferenceException:
            while True:
                try:
                    i = 0 
                    all_leagues = driver.find_elements_by_class_name("ovm-Competition")
                    leagues = find_all_items(all_leagues)
                    break
                except StaleElementReferenceException:
                    print(f'stale element raised {i}')
                    i += 1
        if not current_match:
            break

def get_events(resumo: bool = True) -> List[str]:
    """
    returns a list of events present in "Partida" > "Resumo"
    """
    if not resumo:
        return []

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "ml-StatButtons_Button ")))
    try:
        find_item('resumo', driver.find_elements_by_class_name("ml-StatButtons_Button ")).click() #opens "resumo" tab
    except AttributeError:
        print("There's no resumo tab.")
        return []
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "ml-Summary_Link ")))
        driver.find_element_by_class_name("ml-Summary_Link ").click() #expands to view all events
    except TimeoutException:
        pass #in case there's not enough events to tab to be extendable

    event_list = []
    try:
        WebDriverWait(driver, 5).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, "ml1-SoccerSummaryRow ")))
    except TimeoutException: 
        return event_list #in case there's no events

    events = driver.find_elements_by_class_name("ml1-SoccerSummaryRow ") #gets all events
    
    for event in events:
        event_text = event.text.lower()
        if "'" not in event_text:
            continue
        else:
            event_list.append(event_text)
       
    return event_list

def important_event(time: int) -> bool:
    """checks if gol or card event happened last minute"""
    last_event = get_events(True)[0]
    try:
        time_event = int(last_event.split('\n')[0].strip("'"))
    except ValueError:
        time_event = int(last_event.split('\n')[-1].strip("'"))
    if time - time_event < 60:
        return 'gol' in last_event or 'cartão' in last_event
    return False

def collect_info() -> Tuple[TeamDict, TeamDict, int]:
    """Expects to be in a page with all the info
    returns a tuple (team1, team2, time)
    team1, team2: dict with name, corner kicks, yellow and red cards, penalties and gols 
    time: int in seconds"""
    print('Starting to look for match info')
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "ipe-SoccerGridCell ")))
    match_info = driver.find_elements_by_css_selector('.ipe-SoccerGridCell ')
    name1, name2, gol1, gol2, esc_tot = match_info[0].text.lower(), match_info[1].text.lower(), int(match_info[-2].text), int(match_info[-1].text), int(match_info[2].text) + int(match_info[3].text)

    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "lv-ButtonBar_MatchLiveText "))).click() #opens match info
    except TimeoutException:
        driver.find_element_by_class_name("lv-ButtonBar_ResizeView ").click() #resize tab
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "lv-ButtonBar_MatchLiveText "))).click() #opens "partida" tab
    finally: 
        #TODO what if there's no estatistica/resumo?
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME,"ml-StatButtons_Button ")))
            find_item('estat', driver.find_elements_by_class_name("ml-StatButtons_Button ")).click()
            resumo = True
        except TimeoutException:
            resumo = False
            pass

    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "ml-WheelChart_Container ")))
    info1 = driver.find_elements_by_class_name("ml-WheelChart_Team1Text ")
    info2 = driver.find_elements_by_class_name("ml-WheelChart_Team2Text ")
    try: 
        assert len(info1) > 2
        atq1, atp1, pb1 = int(info1[0].text), int(info1[1].text), float(info1[2].text)
        assert len(info2) > 2
        atq2, atp2, pb2 = int(info2[0].text), int(info2[1].text), float(info2[2].text)
    except AssertionError:
        atq1, atp1, pb1 = int(info1[0].text), int(info1[1].text), 0
        atq2, atp2, pb2 = int(info2[0].text), int(info2[1].text), 0
    
    while True:
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "ml-ProgressBar_MiniBarValue "))) #chute no alvo/ao lado
            # ag_kicks = driver.find_elements_by_class_name("ml-ProgressBar_MiniBarValue ")
            ag_kicks = driver.find_element_by_class_name("ml1-StatsLower ")
            ag_kicks = ag_kicks.text.split('\n')
            break
        except ValueError:
            pass
    ca1, cl1, ca2, cl2 = int(ag_kicks[1]), int(ag_kicks[4]), int(ag_kicks[2]), int(ag_kicks[5])

    time = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "ipe-SoccerHeaderLayout_ExtraData "))).text
    time = convert_time(time)
    
    event_list = get_events(resumo)
    lesc1, lesc2 = 0, 0
    corner_kicks = {name1: [], name2: []}
    for event_text in event_list: #makes a list with all valid corner kicks in order to make bet decisions
        if 'escanteio' in event_text:
                try:
                    lesc = int(event_text.split('\n')[0][:2].strip("'"))
                    if lesc >= lesc1+2:
                        lesc1 = lesc
                        corner_kicks[name1].append(lesc1)
                except ValueError:
                    lesc = int(event_text.split('\n')[-1][:2].strip("'"))
                    if lesc >= lesc2+2:
                        lesc2 = lesc
                        corner_kicks[name2].append(lesc2)

    team1 = {'name': name1,
            'gol': gol1,
            'esc': len(corner_kicks[name1]),
            'atq': atq1,
            'atp': atp1,
            'pb': pb1,
            'ca': ca1,
            'cl': cl1,
            'esc_tot': esc_tot}

    team2 = {'name': name2,
            'gol': gol2,
            'esc': len(corner_kicks[name1]),
            'atq': atq2,
            'atp': atp2,
            'pb': pb2,
            'ca': ca2,
            'cl': cl2,
            'esc_tot': esc_tot}
    return (team1, team2, time)

def favorite() -> Tuple[Union[TeamDict, bool], Union[TeamDict, bool], Union[float, bool], Union[int, bool]]:
    """Expects to be in the page with match info
    returns (info_favorite_team > dict, balanceamento > float, time > int)"""
    if get_time() > 87*60: #if this happens there's no need to look into this match
        time = fav = balan = other = False
        print('Too late into this match. Skipping.')
        return (fav, other, balan, time)

    team1, team2, time = collect_info()
    def calc_criteria(team_info, time=time):
        team_info['appm'] = team_info['atp'] / time*60
        team_info['cg'] = team_info['ca'] + team_info['cl'] + team_info['esc']
        team_info['rend'] = team_info['appm'] * team_info['pb']

    print("Calculating match metrics")
    calc_criteria(team1)
    calc_criteria(team2)

    timer = 10
    while timer:
        try:
            group_tabs = driver.find_elements_by_class_name("sip-MarketGroup ")
            both_odds = find_item('resultado final', group_tabs)
            both_odds = both_odds.find_elements_by_class_name('srb-ParticipantStackedBorderless_Odds')
            timer = 0
        except AttributeError: #when "suspenso" appears this error is raised
            timer -= 1
            sleep(1)
        
    try:
        assert len(both_odds) == 3
        odds = [float(both_odds[0].text), float(both_odds[2].text)] #[0] team1
        balan = max(odds)/min(odds)
        fav = team1 if max(odds) == odds[1] else team2 #sets who is favorite, i.e., who's got the minor odds of winning
        other = team2 if max(odds) == odds[1] else team1
    except (TypeError, ValueError): 
        fav, other = team1, team2
        balan = 0
    fav['balan'] = other['balan'] = balan

    return (fav, other, balan, time)

def match_condition(fav: TeamDict, other: TeamDict, balan: float, time: int, strategy: str) -> bool:
    if strategy == 'h1':
        return all([time > 30*60, 
        time < 45*60, 
        fav['rend'] >= STRATEGIES['h1']['rend'], 
        balan >= STRATEGIES['h1']['balan'], 
        fav['cg']-other['cg'] >= STRATEGIES['h1']['cg']])   
    if strategy == 'e1':
        return all([time > (8*60)+30 and time < (9*60)+30, 
        fav['appm'] >= STRATEGIES[strategy]['appm'],
        fav['cg'] >= STRATEGIES[strategy]['cg']])
    if strategy == 'e11':
        return all([time > (53*60)+30 and time < 54*60,
        fav['appm'] >= STRATEGIES[strategy]['appm'],
        fav['cg'] >= STRATEGIES[strategy]['cg']])
    if strategy == 'e2':
        return all([time > 32*60 and time < 34*60,
        fav['appm'] >= STRATEGIES['e2']['appm'],
        fav['cg'] >= STRATEGIES['e2']['cg']])
    if strategy == 'e3':
        return all([time > 37*60 and time < 39*60,
        fav['appm'] >= STRATEGIES['e3']['appm'],
        fav['cg'] >= STRATEGIES['e3']['cg']])
    if strategy == 'e4':
        return all([time > 74*60 and time < 76*60,
        fav['appm'] >= STRATEGIES['e4']['appm'],
        fav['cg'] >= STRATEGIES['e4']['cg']])
    if strategy == 'e5':
        return all([time > 85*60 and time < 87*60,
        fav['appm'] >= STRATEGIES['e5']['appm'],
        fav['cg'] >= STRATEGIES['e5']['cg']])

def place_bet(fav: TeamDict, strategy: str, line: str, user: User, owned: float, stake: float = STAKE) -> None: #I HAVE TO CHANGE THIS FOR REPORT FUNCTION
    """Expects the bet box to be open
    enters amount to be bet and confirms"""
    bet_stake = STAKE * owned
    bet_stake = "%.2f" %bet_stake
    bet_stake = bet_stake.replace(".", ",")
    #selecting bet
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "bss-StakeBox_StakeAndReturn "))).click() #selects bet value box
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.CLASS_NAME, "bss-StakeBox_StakeAndReturn "), "0,00"))

    #sending bet value
    driver.find_element_by_class_name("bss-StakeBox_StakeValueInput ").send_keys(f'{bet_stake}') # enter bet_stake value
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "bss-PlaceBetButton "))).click() #places bet
    except TimeoutException:
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CLASS_NAME, "bs-AcceptButton "))).click() #accepts changes in bet
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CLASS_NAME, "bss-PlaceBetButton "))).click() #places bet
        except ElementClickInterceptedException:
            tries = 10
            while tries:
                try:
                    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "bs-AcceptButton "))).click() #accepts changes in bet
                    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "bss-PlaceBetButton "))).click()
                    break
                except ElementClickInterceptedException:
                    tries -= 1

    tries = 10
    ##SOMETIMES THERE'S THIS 'TERMINAR BUTTON'
    while tries:
        try:
            # WebDriverWait(driver, 5).until(EC.text_to_be_present_in_element((By.CLASS_NAME, "bs-ReceiptContent_Done "), 'Terminar')) #Does it work?
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "bs-ReceiptContent_Done "))).click() #confirms
            break
        except ElementNotInteractableException:
            tries -= 1
        except TimeoutException:
                break
    
    user.write_pending_bet('bet', fav, strategy, line, datetime.datetime.now())

def place_bet_e1(fav: TeamDict, strategy: str, user: User, time: int, owned: float) -> None: #TODO
    tab = None
    part = "10:00" if time < 10*60 else "55:00"
    group_tabs = driver.find_elements_by_class_name("sip-MarketGroup ") #all markets
    try:
        name_tabs = driver.find_elements_by_class_name("sip-MarketGroupButton_Text ") #all text in markets
        for i, el_tab in enumerate(name_tabs):
            name = el_tab.text.lower()
            if ('escanteio' in name) and ('2' in name) and ('opções' in name) and ('asiático' not in name):
                tab = group_tabs[i] #gets desired market
                j = i
                break 
        assert len(tab.text.split('\n')) > 1 #this happens when tab is closed       
    
    except AssertionError:
        if tab == None:
            print(f'There\'s no bet for {part} kicks')
            return
        tab.click() #if it's closed, it opens
        tab = group_tabs[j]
    
    finally:
        betting_option = "gl-ParticipantCentered " ###TODO CLASS NAME BOTÃO APOSTA
        collumns = tab.find_elements_by_class_name("gl-Market ")
        collumn = find_item(fav['name'], collumns) ###TODO CLASS NAME NOME COLUNA
        ####TODO TESTAR DAQUI PRA BAIXO
        bet_button = find_item('sim', collumn.find_elements_by_class_name(betting_option)) #click on +esc_tot bet, does not check if it's the only one
        bet_button.click()

        place_bet(fav, strategy, 'mais', user, owned)

def place_bet_e24(fav: TeamDict, strategy: str, user: User, time: int, owned: float) -> None:
    """strategy e2 is bet on corner kicks non-asian in the first part and e4 in the second on"""
    part = {'e2': '1', 'e4': '2'}
    tab = None
    group_tabs = driver.find_elements_by_class_name("sip-MarketGroup ") #all markets
    try:
        name_tabs = driver.find_elements_by_class_name("sip-MarketGroupButton_Text ") #all text in markets
        for i, el_tab in enumerate(name_tabs):
            name = el_tab.text.lower()
            if part[strategy] == '2' and ('escanteio' in name) and ('opções' in name):
                tab = group_tabs[i] #gets desired market
                break 
            elif ('escanteio' in name) and (part[strategy] in name) and ('º' in name or 'ª' in name) and ('asiático' not in name):
                tab = group_tabs[i] #gets desired market
                break

        assert len(tab.text.split('\n')) > 1 #this happens when tab is closed       

    except AssertionError:
        tab.click() #if it's closed, it opens
        if tab == None:
            print(f'Não há apostas de handicap para 1º tempo')
            return

    finally:
        rows = tab.find_elements_by_class_name("gl-Market ")[0] #first collumn is bet numbers
        j = None
        for i, row in enumerate(rows.text.split('\n')): #iterates over head text
            row = row.lower()
            if str(fav['esc_tot']+1) in row: #gets what row is bet
                j = i 
                break
        if j == None:
            print(f'Bet on {fav["esc_tot"]+1} not avaible')
            return
        bet_collumn = tab.find_elements_by_class_name("gl-Market ")[1] #"mais de" in collumn 1
        bet_button = bet_collumn.find_elements_by_class_name("gl-ParticipantOddsOnly ")[j] #click on bet option
        bet_button.click()

        place_bet(fav, strategy, 'mais', user, owned)

def place_bet_e35(fav: TeamDict, strategy: str, part: str, bet: List[str], user: User, time: int, owned: float) -> None:
    collumn_dict = {'1': 'exatamente', '1.5': 'mais'}
    tab, line = None, None
    group_tabs = driver.find_elements_by_class_name("sip-MarketGroup ") #all markets
    try:
        name_tabs = driver.find_elements_by_class_name("sip-MarketGroupButton_Text ") #all text in markets
        for i, el_tab in enumerate(name_tabs):
            name = el_tab.text.lower()
            if part == '2':
                if bet[0] == 'asiático':
                    if ('escanteio' in name) and ('asiático' in name) and ('2' not in name):
                        tab = group_tabs[i]
                        break

                else:
                    if ('escanteio' in name) and ('opções' in name):
                        tab = group_tabs[i] #gets desired market
                        break 
            
            elif part == '1':
                if bet[0] == 'asiático':
                    if ('escanteio' in name) and ('1' in name) and ('º' in name or 'ª' in name) and ('asiático' in name):
                        tab = group_tabs[i] #gets desired market
                        break

                elif (bet[1] == '1' or bet[1] == '1.5'):
                    if ('escanteio' in name) and (part in name) and ('º' in name or 'ª' in name) and ('asiático' not in name):
                        tab = group_tabs[i] #gets desired market
                        break

        assert len(tab.text.split('\n')) > 1 #this happens when tab is closed       

    except AssertionError:
        tab.click() #if it's closed, it opens
        if tab == None:
            print(f'This type of bet for {part}º part is not avaiable')
            # return

    finally:
        rows = tab.find_elements_by_class_name("gl-Market ")[0] #first collumn is bet numbers
        i, j = None, None
        for k, row in enumerate(rows.text.split('\n')): #iterates over head text
            row = row.lower()
            if bet[0] == 'asiático':  
                if str(fav['esc_tot']+0.5) in row: #gets what row is desired bet
                    i = k 
                    break
            else:
                if str(int(fav['esc_tot'])+float(bet[1])//1) in row:
                    i = k
                    break
        if i == None:
            print(f'Bet not found')
            return

        for i, collumn in enumerate(tab.find_elements_by_class_name("gl-Market ")): #iterates over head text
            collumn = collumn.text.lower()
            if bet[0] == 'asiático':
                if 'mais de' in collumn: #gets what collumn is bet mode
                    j = i 
                    line = 'mais'
                    break
            else:
                if collumn_dict[bet[1]] in collumn:
                    j = i
                    line = collumn_dict[bet[1]]
                    break
        if j == None:
            print(f'Bet on {fav["esc_tot"]+0.5} not avaible')
            return

        bet_collumn = tab.find_elements_by_class_name("gl-Market ")[j] #"mais de" in collumn 1
        # bet_collumn.find_elements_by_class_name("gl-ParticipantOddsOnly ")[i].click() #click on bet option
        bet_button = bet_collumn.find_element_by_class_name("gl-ParticipantOddsOnly ") #click on bet option THIS HAS JUST ONE LINE
        bet_button.click()

        place_bet(fav, strategy, line, user, owned)

def place_bet_h1(fav: TeamDict, user: User, owned: float) -> None:
    tab = None
    group_tabs = driver.find_elements_by_class_name("sip-MarketGroup ") #all markets
    try:
        name_tabs = driver.find_elements_by_class_name("sip-MarketGroupButton_Text ") #all text in markets
        for i, el_tab in enumerate(name_tabs):
            name = el_tab.text.lower()
            if ('handicap' in name) and ('1' in name) and ('º' in name or 'ª' in name) \
                and ('asiático' in name):
                tab = group_tabs[i] #gets desired market
                break 
        assert len(tab.text.split('\n')) > 1 #this happens when tab is closed       

    except AssertionError:
        tab.click() #if it's closed, it opens
        if tab == None:
            print(f'Não há apostas de handicap para 1º tempo')
            return

    finally:
        betting_option = "gl-ParticipantCentered " #unique to this bet
        collumns = tab.find_elements_by_class_name("gl-Market ")
        collumn = find_item(fav['name'], collumns)
        ####TODO TESTAR DAQUI PRA BAIXO
        bet_button = find_exact1('-0.5', collumn.find_elements_by_class_name(betting_option)) #click on +esc_tot bet, does not check if it's the only one
        bet_button.click()
        
        place_bet(fav, 'h1', fav['name'], user, owned)

def bet(user: User, users_list: List[User]) -> None:
    """Gets all matches there's a possibility of betting, scraps info in match page and calls bet function if needed"""
    for match in search_matches():
        print()
        to_print= ' '.join(match.text.split('\n')[:2])
        print()
        print(f"Looking into {to_print}")
        while True:
            try:
                match.click() #goes to match page
                WebDriverWait(driver, 10).until(EC.url_changes('https://www.bet365.com/#/IP/B1'))
                break
            except TimeoutException:
                pass
        
        fav, other, balan, time = favorite()
        if not time: #if "resultado final" is not displayed or time > 87 min, so there's no bet to be made here
            WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.CLASS_NAME, "ip-ControlBar_BBarItem"))).click()
            continue

        USERS = users_list
        for strategy, params in STRATEGIES.items():
            owned = user.get_money() #inside the loop cause one bet may change this value
            
            #if "resultado final" is not avaiable fav is set based on params. If other has enough appm/cg to bet, it'll be fav
            if strategy != 'h1' and (other['appm'] >= params['appm']) and (other['cg'] >= params['cg']):
                fav = other
            
            if params['state']: #checks if strategy is active
                print(f'Testing strategy {strategy}.', end=" ")
                print(f'appm={fav["appm"]}. cg={fav["cg"]}. rend={fav["rend"]}. balan={balan}. cga-cgb={fav["cg"] - other["cg"]}')
                if time > 10*60 and strategy == 'e1':
                    strategy == 'e11' 

                if (strategy == 'e1' or strategy == 'e11') and match_condition(fav, other, balan, time, strategy) and not important_event(time):
                    print(f'{strategy} approved.')
                    if time < 9*60+30:
                        for user_bet in USERS:
                            while time < 9*60+30:
                                try:
                                    if user_bet != USERS[0]:
                                        print('inside if')
                                        login(user_bet)
                                        owned = user_bet.get_money()
                                    place_bet_e1(fav, strategy, user, time, owned)
                                    time = get_time()
                                    if user_bet.risk_management():
                                        RISK_USERS.append(user_bet)
                                    logout()
                                    break
                                except AttributeError:
                                    pass
                            if get_time() > 9*60+30:
                                break
                        login(user)
                        break
                        
                    else:
                        for user_bet in USERS:
                            while time < 54*60+30:
                                try:
                                    if user_bet != USERS[0]:
                                        login(user_bet)
                                        owned = user.get_money()
                                    place_bet_e1(fav, strategy, user, time, owned)
                                    time = get_time()
                                    if user_bet.risk_management():
                                        RISK_USERS.append(user_bet)
                                    logout()
                                    break
                                except AttributeError:
                                    pass
                            if get_time() > 54*60+30:
                                break
                        login(user)
                        break

                if strategy == 'e2' and (fav['gol'] <= other['gol']) and match_condition(fav, other, balan, time, strategy) and not important_event(time): #checks if gol or card in last minute
                    print(f'{strategy} approved.')
                    for user_bet in USERS:
                        while time < 34*60+30:
                            try:
                                if user_bet != USERS[0]:
                                    login(user_bet)
                                    owned = user.get_money()
                                place_bet_e24(fav, strategy, '1', user, time, owned)
                                time = get_time()
                                if user_bet.risk_management():
                                    RISK_USERS.append(user_bet)
                                logout()
                                break
                            except AttributeError:
                                pass
                        if get_time() > 34*60+30:
                            break
                    login(user)

                if strategy == 'e3' and (fav['gol'] <= other['gol']) and match_condition(fav, other, balan, time, strategy) and not important_event(time):
                    print(f'{strategy} approved.')
                    for user_bet in USERS:
                        while time < 39*60:
                            try:
                                if user_bet != USERS[0]:
                                    login(user_bet)
                                    owned = user.get_money()
                                place_bet_e35(fav, strategy, '1', ['asiático'], user, time, owned)
                                time = get_time()
                                while time < 39*60:
                                    place_bet_e35(fav, strategy, '1', ['não asiático', '1.0'], user, time, owned)
                                    time = get_time()
                                    while time < 39*60:
                                        place_bet_e35(fav, strategy, '1', ['não asiático', '1.5'], user, time, owned)
                                        time = get_time()
                                    if user_bet.risk_management():
                                        RISK_USERS.append(user_bet)
                                    logout()
                                    break
                            except AttributeError:
                                pass    
                        if get_time() > 39*60:
                            break
                    login(user)

                if strategy == 'e4' and (fav['gol'] <= other['gol']) and match_condition(fav, other, balan, time, strategy) and not important_event(time):
                    print(f'{strategy} approved.')
                    for user_bet in USERS:
                        while time < 76*60:
                            if user_bet != USERS[0]:
                                login(user_bet)
                                owned = user.get_money()
                            place_bet_e24(fav, strategy, '2', user, time, owned)
                            time = get_time()
                            if user_bet.risk_management():
                                RISK_USERS.append(user_bet)
                            logout()
                            break
                        if get_time() > 76*60:
                            break
                    login(user)
                    
                if strategy == 'e5' and (fav['gol'] <= other['gol']) and match_condition(fav, other, balan, time, strategy) and not important_event(time):
                    print(f'{strategy} approved.')
                    for user_bet in USERS:
                        while time < 87*60:
                            try:
                                if user_bet != USERS[0]:
                                    login(user_bet)
                                    owned = user.get_money()
                                place_bet_e35(fav, strategy, '2', ['asiático'], user, time, owned)
                                time = get_time()
                                while time < 87*60:
                                    place_bet_e35(fav, strategy, '2', ['não asiático', '1.0'], user, time, owned)
                                    time = get_time()
                                    while time < 87*60:
                                        place_bet_e35(fav, strategy, '2', ['não asiático', '1.5'], user, time, owned)
                                        time = get_time()
                                        break
                                    break
                                if user_bet.risk_management():
                                    RISK_USERS.append(user_bet)
                                logout()
                                break
                            except AttributeError:
                                pass    
                        if get_time() > 39*60:
                            break
                    login(user)
                
                if strategy == 'h1' and match_condition(fav, other, balan, time, strategy):
                    print(f'{strategy} approved.')
                    for user_bet in USERS:
                        if user_bet != USERS[0]:
                            login(user_bet)
                        time_limit = datetime.datetime.now() + datetime.timedelta(seconds=15)
                        while datetime.datetime.now() < time_limit:
                            try:
                                place_bet_h1(fav, user, owned)
                                break
                            except AttributeError:
                                pass
                
                USERS = list(filter(lambda user: user not in RISK_USERS, USERS)) #filters users
        WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.CLASS_NAME, "ip-ControlBar_BBarItem"))).click() #returns to all live matches page


info_accounts = init_accounts('credentials.txt')

#PROGRAM ITSELF
for username, password in info_accounts.items():
    USERS.append(User(username, password))

login(USERS[0])
while len(USERS):
    user = USERS[0]
    bet(user, USERS)
    
    #quits if person clicks on pygame X
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            print('User request to shut down')
            if len(USERS) == 0:
                break
            user.write_report()
            logout()
            USERS.pop(0)
            for i in range(len(USERS)):
                user = USERS.pop(0)
                login(user)
                user.write_report()
                logout()
            driver.quit()
            continue
    
    #if the logged account returns True risk_management(), writes report, logout and removes user from USERS
    if user.risk_management():
        user.write_report()
        logout()
        USERS.pop(0)
        login(USERS[0])
    
    #writes report for all accounts that stopped betting because of risk_management()
    if len(RISK_USERS) != 0:
        logout()
        for risk_user in RISK_USERS:
            login(risk_user)
            risk_user.write_report()
            logout()
        login(USERS[0])

    #writes report if has passed REPORT_FREQ hours since last one 
    if datetime.datetime.now() - REPORT_FREQ > user.last_report:
        for user in USERS:
            if user != USERS[0]:
                login(user)
            user.write_report()
            logout()